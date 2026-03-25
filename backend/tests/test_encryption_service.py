"""
Tests para EncryptionService - Servicio de Encriptacion.

Cobertura de encriptacion, desencriptacion y manejo de claves.
"""

import pytest
from unittest.mock import Mock, patch
import base64

from app.services.encryption_service import (
    EncryptionService,
    EncryptionError,
)


class TestEncryptionError:
    """Tests para excepcion EncryptionError."""

    def test_encryption_error_creation(self):
        """Test creacion de EncryptionError."""
        error = EncryptionError("Test error message")
        assert str(error) == "Test error message"

    def test_encryption_error_inheritance(self):
        """Test que hereda de Exception."""
        error = EncryptionError("Test")
        assert isinstance(error, Exception)


class TestEncryptionServiceInit:
    """Tests para inicializacion de EncryptionService."""

    def test_init_without_master_key(self):
        """Test inicializacion sin master key usa key de desarrollo."""
        with patch.dict('os.environ', {'ENCRYPTION_MASTER_KEY': ''}, clear=False):
            service = EncryptionService()
            assert service._master_key is not None
            assert service._fernet is not None

    def test_init_with_master_key(self):
        """Test inicializacion con master key."""
        # Generar una key valida
        from cryptography.fernet import Fernet
        valid_key = Fernet.generate_key().decode()

        service = EncryptionService(master_key=valid_key)
        assert service._master_key == valid_key
        assert service._fernet is not None


class TestEncryptionServiceKeyGeneration:
    """Tests para generacion de claves."""

    def test_generate_dev_key(self):
        """Test generacion de clave de desarrollo."""
        key = EncryptionService._generate_dev_key()
        assert key is not None
        assert len(key) > 0
        # Verificar que es base64 valido
        decoded = base64.urlsafe_b64decode(key)
        assert len(decoded) == 32  # SHA256 produce 32 bytes

    def test_generate_dev_key_deterministic(self):
        """Test que la clave de desarrollo es deterministica."""
        key1 = EncryptionService._generate_dev_key()
        key2 = EncryptionService._generate_dev_key()
        assert key1 == key2

    def test_generate_master_key(self):
        """Test generacion de master key segura."""
        key = EncryptionService.generate_master_key()
        assert key is not None
        assert len(key) == 44  # Fernet keys son 44 caracteres en base64

    def test_generate_master_key_unique(self):
        """Test que cada master key es unica."""
        key1 = EncryptionService.generate_master_key()
        key2 = EncryptionService.generate_master_key()
        assert key1 != key2


class TestEncryptionServiceEncryption:
    """Tests para encriptacion/desencriptacion."""

    @pytest.fixture
    def service(self):
        """Crea instancia del servicio."""
        return EncryptionService()

    def test_encrypt_decrypt_roundtrip(self, service):
        """Test encriptar y desencriptar."""
        original = "datos sensibles de prueba"
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_returns_different_from_original(self, service):
        """Test que encriptado es diferente del original."""
        original = "texto original"
        encrypted = service.encrypt(original)
        assert encrypted != original

    def test_encrypt_empty_string_raises(self, service):
        """Test que encriptar string vacio lanza error."""
        with pytest.raises(EncryptionError):
            service.encrypt("")

    def test_encrypt_unicode(self, service):
        """Test encriptar caracteres unicode."""
        original = "Texto con acentos: áéíóú ñ"
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)
        assert decrypted == original


class TestEncryptionServicePrivateKey:
    """Tests para encriptacion de llaves privadas."""

    @pytest.fixture
    def service(self):
        """Crea instancia del servicio."""
        return EncryptionService()

    def test_encrypt_private_key(self, service):
        """Test encriptar llave privada."""
        private_key = "0x" + "a" * 64  # Formato de private key ETH
        encrypted = service.encrypt_private_key(private_key)
        decrypted = service.decrypt_private_key(encrypted)
        assert decrypted == "0x" + "a" * 64

    def test_encrypt_private_key_without_prefix(self, service):
        """Test encriptar llave privada sin prefijo 0x."""
        private_key = "b" * 64
        encrypted = service.encrypt_private_key(private_key)
        decrypted = service.decrypt_private_key(encrypted)
        assert decrypted == "0x" + "b" * 64

    def test_encrypt_invalid_private_key_length(self, service):
        """Test error con llave privada de longitud invalida."""
        with pytest.raises(EncryptionError):
            service.encrypt_private_key("0x123")

    def test_encrypt_invalid_private_key_format(self, service):
        """Test error con llave privada no hex."""
        with pytest.raises(EncryptionError):
            service.encrypt_private_key("0x" + "g" * 64)  # 'g' no es hex


class TestEncryptionServiceDecryption:
    """Tests para errores de desencriptacion."""

    @pytest.fixture
    def service(self):
        """Crea instancia del servicio."""
        return EncryptionService()

    def test_decrypt_empty_string_raises(self, service):
        """Test que desencriptar string vacio lanza error."""
        with pytest.raises(EncryptionError):
            service.decrypt("")

    def test_decrypt_invalid_token(self, service):
        """Test desencriptar token invalido."""
        with pytest.raises(EncryptionError):
            service.decrypt("token_invalido_no_base64_!")

    def test_decrypt_wrong_key(self):
        """Test desencriptar con clave incorrecta."""
        service1 = EncryptionService()
        service2 = EncryptionService(
            master_key=EncryptionService.generate_master_key()
        )

        original = "datos secretos"
        encrypted = service1.encrypt(original)

        # Intentar desencriptar con otra clave deberia fallar
        with pytest.raises(EncryptionError):
            service2.decrypt(encrypted)


class TestEncryptionServiceFernetCreation:
    """Tests para creacion de Fernet."""

    def test_create_fernet_with_valid_key(self):
        """Test crear Fernet con clave valida."""
        from cryptography.fernet import Fernet
        valid_key = Fernet.generate_key().decode()
        service = EncryptionService(master_key=valid_key)
        assert service._fernet is not None

    def test_create_fernet_with_derived_key(self):
        """Test crear Fernet derivando clave."""
        # Clave que no es formato Fernet (44 chars)
        short_key = "my-secret-key"
        service = EncryptionService(master_key=short_key)
        assert service._fernet is not None
