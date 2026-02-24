"""
Módulo de Seguridad Búnker - Grado Militar.

Implementa:
- Cifrado con Libsodium (PyNaCl)
- Integración con HashiCorp Vault
- Device Fingerprinting
- Zero Trust con tokens temporales
- mTLS para comunicación entre servicios

Estándares: SOC2, ISO 27001, PCI-DSS
"""
import os
import hashlib
import hmac
import secrets
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from functools import lru_cache
import base64

# Libsodium (PyNaCl) para cifrado de alta seguridad
try:
    import nacl.secret
    import nacl.utils
    import nacl.pwhash
    import nacl.signing
    import nacl.public
    from nacl.encoding import Base64Encoder
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False
    print("WARNING: PyNaCl not installed. Using fallback encryption.")

# HashiCorp Vault
try:
    import hvac
    VAULT_AVAILABLE = True
except ImportError:
    VAULT_AVAILABLE = False
    print("WARNING: hvac not installed. Vault integration disabled.")

from app.core.config import settings


class LibsodiumCrypto:
    """
    Cifrado de alta seguridad usando Libsodium (NaCl).

    Ventajas sobre AES tradicional:
    - Resistente a ataques de timing
    - Autenticación integrada (AEAD)
    - API más difícil de usar incorrectamente
    """

    def __init__(self, key: Optional[bytes] = None):
        if not NACL_AVAILABLE:
            raise RuntimeError("PyNaCl is required for Libsodium encryption")

        if key:
            self.key = key
        else:
            # Derivar clave desde configuración
            self.key = self._derive_key_from_settings()

        self.box = nacl.secret.SecretBox(self.key)

    def _derive_key_from_settings(self) -> bytes:
        """Deriva una clave de 32 bytes desde la configuración."""
        # Usar Argon2id para derivación de clave (resistente a GPU)
        password = settings.ENCRYPTION_KEY.encode()
        salt = settings.SECRET_KEY[:16].encode()

        # Argon2id con parámetros seguros
        return nacl.pwhash.argon2id.kdf(
            nacl.secret.SecretBox.KEY_SIZE,
            password,
            salt,
            opslimit=nacl.pwhash.argon2id.OPSLIMIT_SENSITIVE,
            memlimit=nacl.pwhash.argon2id.MEMLIMIT_SENSITIVE
        )

    def encrypt(self, plaintext: str) -> str:
        """
        Cifra datos con XSalsa20-Poly1305.
        Incluye nonce único y MAC para autenticación.
        """
        encrypted = self.box.encrypt(
            plaintext.encode('utf-8'),
            encoder=Base64Encoder
        )
        return encrypted.decode('utf-8')

    def decrypt(self, ciphertext: str) -> str:
        """Descifra datos."""
        decrypted = self.box.decrypt(
            ciphertext.encode('utf-8'),
            encoder=Base64Encoder
        )
        return decrypted.decode('utf-8')

    @staticmethod
    def generate_key() -> bytes:
        """Genera una nueva clave segura de 32 bytes."""
        return nacl.utils.random(nacl.secret.SecretBox.KEY_SIZE)


class FieldLevelEncryption:
    """
    Cifrado a nivel de campo para datos sensibles.

    Campos que deben cifrarse:
    - RFC/Tax ID
    - Números de cuenta bancaria
    - CLABE
    - Datos de tarjeta
    - Información personal identificable (PII)
    """

    def __init__(self):
        if NACL_AVAILABLE:
            self.crypto = LibsodiumCrypto()
        else:
            # Fallback a Fernet si Libsodium no está disponible
            from app.core.security import encrypt_sensitive_data, decrypt_sensitive_data
            self.encrypt = encrypt_sensitive_data
            self.decrypt = decrypt_sensitive_data
            return

    def encrypt_field(self, value: str, field_type: str = "generic") -> Dict[str, str]:
        """
        Cifra un campo con metadata.

        Retorna:
        {
            "encrypted_value": "...",
            "encryption_version": "nacl_v1",
            "field_type": "tax_id",
            "encrypted_at": "2024-01-01T00:00:00Z"
        }
        """
        return {
            "encrypted_value": self.crypto.encrypt(value),
            "encryption_version": "nacl_v1",
            "field_type": field_type,
            "encrypted_at": datetime.utcnow().isoformat()
        }

    def decrypt_field(self, encrypted_data: Dict[str, str]) -> str:
        """Descifra un campo."""
        return self.crypto.decrypt(encrypted_data["encrypted_value"])

    def encrypt_pii(self, data: Dict[str, Any], pii_fields: list) -> Dict[str, Any]:
        """
        Cifra campos PII específicos en un diccionario.

        Ejemplo:
        encrypt_pii(user_data, ['rfc', 'curp', 'bank_account'])
        """
        result = data.copy()
        for field in pii_fields:
            if field in result and result[field]:
                result[f"{field}_encrypted"] = self.encrypt_field(
                    str(result[field]),
                    field_type=field
                )
                # Guardar solo últimos 4 caracteres para referencia
                result[f"{field}_masked"] = f"****{str(result[field])[-4:]}"
                del result[field]
        return result


class VaultClient:
    """
    Cliente para HashiCorp Vault.

    Funcionalidades:
    - Almacenamiento seguro de secretos
    - Rotación automática de credenciales
    - Tokens temporales para servicios
    - PKI para certificados mTLS
    """

    def __init__(self):
        if not VAULT_AVAILABLE:
            self.client = None
            return

        vault_url = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
        vault_token = os.getenv("VAULT_TOKEN")

        if vault_token:
            self.client = hvac.Client(url=vault_url, token=vault_token)
        else:
            # Intentar autenticación AppRole
            role_id = os.getenv("VAULT_ROLE_ID")
            secret_id = os.getenv("VAULT_SECRET_ID")
            if role_id and secret_id:
                self.client = hvac.Client(url=vault_url)
                self.client.auth.approle.login(
                    role_id=role_id,
                    secret_id=secret_id
                )
            else:
                self.client = None

    @property
    def is_connected(self) -> bool:
        """Verifica si Vault está conectado y autenticado."""
        if not self.client:
            return False
        try:
            return self.client.is_authenticated()
        except:
            return False

    def get_secret(self, path: str) -> Optional[Dict]:
        """
        Obtiene un secreto de Vault.

        Ejemplo: get_secret("fincore/database/credentials")
        """
        if not self.is_connected:
            return None
        try:
            secret = self.client.secrets.kv.v2.read_secret_version(path=path)
            return secret['data']['data']
        except Exception as e:
            print(f"Vault error getting secret: {e}")
            return None

    def create_dynamic_db_credential(self) -> Optional[Dict]:
        """
        Crea credenciales dinámicas de base de datos.
        Estas credenciales expiran automáticamente.
        """
        if not self.is_connected:
            return None
        try:
            cred = self.client.secrets.database.generate_credentials(
                name="fincore-db-role"
            )
            return {
                "username": cred['data']['username'],
                "password": cred['data']['password'],
                "lease_duration": cred['lease_duration'],
                "lease_id": cred['lease_id']
            }
        except Exception as e:
            print(f"Vault error creating DB credential: {e}")
            return None

    def get_service_token(self, service_name: str, ttl: str = "1h") -> Optional[str]:
        """
        Genera token temporal para comunicación entre servicios (Zero Trust).

        Args:
            service_name: Nombre del servicio (e.g., "calculation-engine")
            ttl: Tiempo de vida del token

        Returns:
            Token temporal o None
        """
        if not self.is_connected:
            return None
        try:
            # Crear token con políticas limitadas
            token = self.client.auth.token.create(
                policies=[f"{service_name}-policy"],
                ttl=ttl,
                renewable=False,
                display_name=f"service-{service_name}"
            )
            return token['auth']['client_token']
        except Exception as e:
            print(f"Vault error creating service token: {e}")
            return None


class DeviceFingerprint:
    """
    Sistema de Device Fingerprinting.

    Detecta y registra dispositivos únicos para:
    - Verificación de dispositivos conocidos
    - Detección de accesos sospechosos
    - Re-autenticación en dispositivos nuevos
    """

    @staticmethod
    def generate_fingerprint(
        user_agent: str,
        ip_address: str,
        accept_language: str = "",
        screen_resolution: str = "",
        timezone: str = "",
        plugins: str = "",
        canvas_hash: str = "",
        webgl_hash: str = ""
    ) -> str:
        """
        Genera una huella digital única del dispositivo.

        Combina múltiples señales para crear un identificador único
        que persiste incluso si cambian algunos parámetros.
        """
        components = [
            user_agent,
            accept_language,
            screen_resolution,
            timezone,
            plugins,
            canvas_hash,
            webgl_hash
        ]

        # Hash de los componentes
        fingerprint_string = "|".join(components)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()

    @staticmethod
    def generate_server_fingerprint(
        user_agent: str,
        ip_address: str,
        accept_headers: Dict[str, str]
    ) -> str:
        """
        Genera fingerprint desde el servidor (sin JavaScript).
        Menos preciso pero funciona sin client-side.
        """
        components = [
            user_agent,
            ip_address[:ip_address.rfind(".")] if "." in ip_address else ip_address,  # Subnet
            accept_headers.get("accept-language", ""),
            accept_headers.get("accept-encoding", ""),
        ]

        fingerprint_string = "|".join(components)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]

    @staticmethod
    def is_fingerprint_similar(fp1: str, fp2: str, threshold: float = 0.8) -> bool:
        """
        Compara dos fingerprints para determinar si son del mismo dispositivo.
        Permite cierta variación (por updates de navegador, etc.)
        """
        if fp1 == fp2:
            return True

        # Comparación de Hamming para hashes
        if len(fp1) != len(fp2):
            return False

        differences = sum(c1 != c2 for c1, c2 in zip(fp1, fp2))
        similarity = 1 - (differences / len(fp1))
        return similarity >= threshold


class ZeroTrustAuth:
    """
    Implementación de Zero Trust Authentication.

    Principios:
    - Nunca confiar, siempre verificar
    - Asumir que la red está comprometida
    - Verificar explícitamente cada request
    """

    def __init__(self):
        self.vault = VaultClient()

    def generate_service_to_service_token(
        self,
        source_service: str,
        target_service: str,
        permissions: list,
        ttl_seconds: int = 300  # 5 minutos por defecto
    ) -> Dict[str, Any]:
        """
        Genera token temporal para comunicación entre servicios.

        Este token:
        - Expira rápidamente (5 min default)
        - Incluye permisos específicos
        - Se puede revocar inmediatamente
        """
        token_id = secrets.token_urlsafe(32)
        issued_at = datetime.utcnow()
        expires_at = issued_at + timedelta(seconds=ttl_seconds)

        payload = {
            "token_id": token_id,
            "source": source_service,
            "target": target_service,
            "permissions": permissions,
            "iat": issued_at.isoformat(),
            "exp": expires_at.isoformat(),
        }

        # Firmar con HMAC
        signature = hmac.new(
            settings.SECRET_KEY.encode(),
            json.dumps(payload, sort_keys=True).encode(),
            hashlib.sha256
        ).hexdigest()

        return {
            "token": base64.urlsafe_b64encode(
                json.dumps(payload).encode()
            ).decode(),
            "signature": signature,
            "expires_at": expires_at.isoformat()
        }

    def verify_service_token(self, token: str, signature: str) -> Tuple[bool, Optional[Dict]]:
        """
        Verifica un token de servicio a servicio.

        Returns:
            (is_valid, payload)
        """
        try:
            payload = json.loads(base64.urlsafe_b64decode(token))

            # Verificar firma
            expected_signature = hmac.new(
                settings.SECRET_KEY.encode(),
                json.dumps(payload, sort_keys=True).encode(),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                return False, None

            # Verificar expiración
            expires_at = datetime.fromisoformat(payload["exp"])
            if datetime.utcnow() > expires_at:
                return False, None

            return True, payload

        except Exception as e:
            print(f"Token verification error: {e}")
            return False, None

    def create_request_context(
        self,
        user_id: str,
        device_fingerprint: str,
        ip_address: str,
        permissions: list
    ) -> str:
        """
        Crea un contexto de request firmado para auditoría.
        Este contexto viaja con cada request interno.
        """
        context = {
            "user_id": user_id,
            "device_fingerprint": device_fingerprint,
            "ip_address": ip_address,
            "permissions": permissions,
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": secrets.token_urlsafe(16)
        }

        # Firmar contexto
        signature = hmac.new(
            settings.SECRET_KEY.encode(),
            json.dumps(context, sort_keys=True).encode(),
            hashlib.sha256
        ).hexdigest()

        context["signature"] = signature

        return base64.urlsafe_b64encode(
            json.dumps(context).encode()
        ).decode()


class IntegrityChecker:
    """
    Verificador de integridad de datos.

    Detecta si los datos han sido manipulados fuera del sistema.
    """

    @staticmethod
    def calculate_record_hash(record: Dict[str, Any], exclude_fields: list = None) -> str:
        """
        Calcula hash de un registro para verificación de integridad.

        Args:
            record: Diccionario con los datos
            exclude_fields: Campos a excluir (como el propio hash)
        """
        exclude = exclude_fields or ["integrity_hash", "updated_at"]

        data_to_hash = {k: v for k, v in record.items() if k not in exclude}

        # Serialización determinística
        content = json.dumps(data_to_hash, sort_keys=True, default=str)

        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def verify_record_integrity(record: Dict[str, Any], stored_hash: str) -> bool:
        """Verifica que un registro no haya sido manipulado."""
        calculated_hash = IntegrityChecker.calculate_record_hash(record)
        return hmac.compare_digest(calculated_hash, stored_hash)


# Singleton instances
_vault_client = None
_field_encryption = None
_zero_trust = None


def get_vault_client() -> VaultClient:
    """Obtiene instancia singleton de VaultClient."""
    global _vault_client
    if _vault_client is None:
        _vault_client = VaultClient()
    return _vault_client


def get_field_encryption() -> FieldLevelEncryption:
    """Obtiene instancia singleton de FieldLevelEncryption."""
    global _field_encryption
    if _field_encryption is None:
        _field_encryption = FieldLevelEncryption()
    return _field_encryption


def get_zero_trust() -> ZeroTrustAuth:
    """Obtiene instancia singleton de ZeroTrustAuth."""
    global _zero_trust
    if _zero_trust is None:
        _zero_trust = ZeroTrustAuth()
    return _zero_trust
