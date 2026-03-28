"""
Servicio de Encriptación para FinCore.
Maneja encriptación de llaves privadas y datos sensibles usando Fernet (AES-128-CBC).
CRÍTICO: La ENCRYPTION_KEY debe almacenarse en un KMS externo en producción.
"""
import os
import base64
import hashlib
import secrets
import logging
from typing import Optional, Tuple
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Error de encriptación."""
    pass


class EncryptionService:
    """
    Servicio de encriptación para datos sensibles.
    Usa Fernet (AES-128-CBC con HMAC) para encriptación simétrica.

    IMPORTANTE:
    - En producción, la master key debe venir de AWS KMS, HashiCorp Vault, etc.
    - La key NUNCA debe estar en el código fuente o en variables de entorno sin protección.
    - Cada dato encriptado tiene su propio IV único.
    """

    def __init__(self, master_key: Optional[str] = None):
        """
        Inicializa el servicio de encriptación.

        Args:
            master_key: Clave maestra en formato base64 (32 bytes encoded).
                       Si no se proporciona, usa ENCRYPTION_MASTER_KEY del entorno.
        """
        self._master_key = master_key or os.getenv("ENCRYPTION_MASTER_KEY")

        if not self._master_key:
            # En desarrollo, generar una clave temporal (NO USAR EN PRODUCCIÓN)
            logger.warning(
                "⚠️ ENCRYPTION_MASTER_KEY no configurada. "
                "Usando clave temporal. NO USAR EN PRODUCCIÓN."
            )
            self._master_key = self._generate_dev_key()

        # Derivar la clave Fernet de la master key
        self._fernet = self._create_fernet(self._master_key)

    @staticmethod
    def _generate_dev_key() -> str:
        """
        Genera una clave de desarrollo ALEATORIA.
        ADVERTENCIA: Esta clave cambia en cada reinicio del servicio.
        Los datos encriptados no podrán ser recuperados después de reiniciar.
        SOLO para desarrollo local - NO USAR EN PRODUCCIÓN.
        """
        logger.warning(
            "⚠️ SEGURIDAD: Generando clave de encriptación temporal aleatoria. "
            "Los datos encriptados se perderán al reiniciar el servicio. "
            "Configure ENCRYPTION_MASTER_KEY para persistencia."
        )
        # Generar clave aleatoria segura (NO determinística)
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()

    @staticmethod
    def generate_master_key() -> str:
        """
        Genera una nueva master key segura.
        Usar esto para generar la key que irá en el KMS.

        Returns:
            Master key en formato base64.
        """
        return Fernet.generate_key().decode()

    def _create_fernet(self, master_key: str, salt: Optional[bytes] = None) -> Fernet:
        """
        Crea una instancia de Fernet a partir de la master key.

        Args:
            master_key: Clave en formato base64.
            salt: Salt para derivación PBKDF2. Si no se proporciona, se genera uno
                  basado en el hash de la master key (determinístico pero único por key).

        Returns:
            Instancia de Fernet.
        """
        try:
            # Si la key ya está en formato Fernet válido (44 chars base64)
            if len(master_key) == 44:
                return Fernet(master_key.encode())

            # Generar salt derivado de la master key si no se proporciona
            # Esto es determinístico para la misma key, pero único por key
            if salt is None:
                # Usar los primeros 16 bytes del hash SHA-256 de la key como salt
                salt = hashlib.sha256(f"fincore-salt-{master_key}".encode()).digest()[:16]

            # Derivar una key Fernet usando PBKDF2 con salt dinámico
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(
                kdf.derive(master_key.encode())
            )
            return Fernet(key)

        except Exception as e:
            logger.error(f"Error creating Fernet instance: {e}")
            raise EncryptionError(f"Invalid master key format: {e}")

    def encrypt(self, plaintext: str) -> str:
        """
        Encripta un string.

        Args:
            plaintext: Texto a encriptar.

        Returns:
            Texto encriptado en formato base64.
        """
        if not plaintext:
            raise EncryptionError("Cannot encrypt empty string")

        try:
            encrypted = self._fernet.encrypt(plaintext.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise EncryptionError(f"Failed to encrypt data: {e}")

    def decrypt(self, ciphertext: str) -> str:
        """
        Desencripta un string.

        Args:
            ciphertext: Texto encriptado en formato base64.

        Returns:
            Texto desencriptado.
        """
        if not ciphertext:
            raise EncryptionError("Cannot decrypt empty string")

        try:
            decrypted = self._fernet.decrypt(ciphertext.encode())
            return decrypted.decode()
        except InvalidToken:
            logger.error("Invalid token - wrong key or corrupted data")
            raise EncryptionError("Decryption failed - invalid token")
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise EncryptionError(f"Failed to decrypt data: {e}")

    def encrypt_private_key(self, private_key: str) -> str:
        """
        Encripta una llave privada de blockchain.
        Agrega validación específica para llaves privadas.

        Args:
            private_key: Llave privada en formato hex (con o sin 0x).

        Returns:
            Llave encriptada.
        """
        # Normalizar formato (quitar 0x si existe)
        key = private_key.lower()
        if key.startswith("0x"):
            key = key[2:]

        # Validar que sea una llave privada válida (64 caracteres hex)
        if len(key) != 64:
            raise EncryptionError(
                f"Invalid private key length: expected 64 hex chars, got {len(key)}"
            )

        if not all(c in "0123456789abcdef" for c in key):
            raise EncryptionError("Invalid private key format: not valid hex")

        return self.encrypt(key)

    def decrypt_private_key(self, encrypted_key: str) -> str:
        """
        Desencripta una llave privada de blockchain.

        Args:
            encrypted_key: Llave encriptada.

        Returns:
            Llave privada en formato hex con prefijo 0x.
        """
        decrypted = self.decrypt(encrypted_key)
        return f"0x{decrypted}"

    def rotate_key(self, new_master_key: str, encrypted_data: str) -> str:
        """
        Re-encripta datos con una nueva master key.
        Usado para rotación de claves.

        Args:
            new_master_key: Nueva master key.
            encrypted_data: Datos encriptados con la key actual.

        Returns:
            Datos encriptados con la nueva key.
        """
        # Desencriptar con la key actual
        plaintext = self.decrypt(encrypted_data)

        # Crear nuevo encriptador
        new_service = EncryptionService(new_master_key)

        # Re-encriptar con la nueva key
        return new_service.encrypt(plaintext)

    @staticmethod
    def generate_secure_password(length: int = 32) -> str:
        """
        Genera una contraseña segura.

        Args:
            length: Longitud de la contraseña.

        Returns:
            Contraseña segura.
        """
        return secrets.token_urlsafe(length)

    @staticmethod
    def hash_for_comparison(data: str) -> str:
        """
        Genera un hash para comparación (no reversible).
        Útil para verificar datos sin almacenar el original.

        Args:
            data: Datos a hashear.

        Returns:
            Hash SHA-256 en formato hex.
        """
        return hashlib.sha256(data.encode()).hexdigest()


# Singleton para uso global
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    Obtiene la instancia singleton del servicio de encriptación.

    Returns:
        Instancia de EncryptionService.
    """
    global _encryption_service

    if _encryption_service is None:
        _encryption_service = EncryptionService()

    return _encryption_service


def encrypt_private_key(private_key: str) -> str:
    """Shortcut para encriptar llave privada."""
    return get_encryption_service().encrypt_private_key(private_key)


def decrypt_private_key(encrypted_key: str) -> str:
    """Shortcut para desencriptar llave privada."""
    return get_encryption_service().decrypt_private_key(encrypted_key)
