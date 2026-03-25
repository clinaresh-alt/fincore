"""
Tests para DocumentVault - Vault Seguro de Documentos.

Cobertura de cifrado, hash y dataclasses.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from decimal import Decimal

from app.services.document_vault import (
    DocumentVault,
    DocumentoSubido,
    ResultadoOCR,
)


class TestDocumentoSubidoDataclass:
    """Tests para dataclass DocumentoSubido."""

    def test_documento_subido_creation(self):
        """Test creacion de DocumentoSubido."""
        doc = DocumentoSubido(
            documento_id="doc-123",
            s3_key="users/123/documentos/ine.pdf",
            s3_bucket="fincore-documents",
            tamano_bytes=1024000,
            hash_sha256="abc123def456",
            cifrado=True,
            fecha_subida=datetime.utcnow()
        )
        assert doc.documento_id == "doc-123"
        assert doc.cifrado is True
        assert doc.tamano_bytes == 1024000

    def test_documento_subido_s3_key_format(self):
        """Test formato de s3_key."""
        doc = DocumentoSubido(
            documento_id="doc-456",
            s3_key="users/user-id/kyc/passport.jpg",
            s3_bucket="fincore-docs",
            tamano_bytes=512000,
            hash_sha256="xyz789",
            cifrado=True,
            fecha_subida=datetime.utcnow()
        )
        assert "users/" in doc.s3_key
        assert doc.s3_key.endswith(".jpg")


class TestResultadoOCRDataclass:
    """Tests para dataclass ResultadoOCR."""

    def test_resultado_ocr_creation(self):
        """Test creacion de ResultadoOCR."""
        ocr = ResultadoOCR(
            texto_extraido="NOMBRE: JUAN PEREZ\nFECHA: 01/01/1990",
            confianza=95,
            campos_detectados={
                "nombre": "JUAN PEREZ",
                "fecha_nacimiento": "01/01/1990"
            },
            fecha_procesamiento=datetime.utcnow()
        )
        assert "JUAN PEREZ" in ocr.texto_extraido
        assert ocr.confianza == 95
        assert "nombre" in ocr.campos_detectados

    def test_resultado_ocr_confianza_range(self):
        """Test rango de confianza 0-100."""
        ocr_bajo = ResultadoOCR(
            texto_extraido="...",
            confianza=10,
            campos_detectados={},
            fecha_procesamiento=datetime.utcnow()
        )
        assert ocr_bajo.confianza >= 0

        ocr_alto = ResultadoOCR(
            texto_extraido="Texto claro",
            confianza=99,
            campos_detectados={"field": "value"},
            fecha_procesamiento=datetime.utcnow()
        )
        assert ocr_alto.confianza <= 100


class TestDocumentVaultConstants:
    """Tests para constantes de DocumentVault."""

    def test_extensiones_permitidas(self):
        """Test extensiones de archivo permitidas."""
        assert ".pdf" in DocumentVault.EXTENSIONES_PERMITIDAS
        assert ".png" in DocumentVault.EXTENSIONES_PERMITIDAS
        assert ".jpg" in DocumentVault.EXTENSIONES_PERMITIDAS
        assert ".jpeg" in DocumentVault.EXTENSIONES_PERMITIDAS

    def test_tamano_maximo(self):
        """Test limite de tamano."""
        assert DocumentVault.TAMANO_MAXIMO_MB > 0
        assert DocumentVault.TAMANO_MAXIMO_MB <= 50  # Razonable para documentos


class TestDocumentVaultInit:
    """Tests para inicializacion de DocumentVault."""

    @patch('app.services.document_vault.boto3')
    @patch('app.services.document_vault.settings')
    def test_init_with_aws_credentials(self, mock_settings, mock_boto3):
        """Test inicializacion con credenciales AWS."""
        mock_settings.AWS_ACCESS_KEY_ID = "test-key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "test-secret"
        mock_settings.AWS_REGION = "us-east-1"
        mock_settings.ENCRYPTION_KEY = "test-encryption-key-32chars!!"

        vault = DocumentVault()
        assert vault is not None
        mock_boto3.client.assert_called_once()

    @patch('app.services.document_vault.boto3')
    @patch('app.services.document_vault.settings')
    def test_init_without_aws_credentials(self, mock_settings, mock_boto3):
        """Test inicializacion sin credenciales AWS."""
        mock_settings.AWS_ACCESS_KEY_ID = None
        mock_settings.ENCRYPTION_KEY = "test-encryption-key-32chars!!"

        vault = DocumentVault()
        assert vault.s3_client is None


class TestDocumentVaultCifrado:
    """Tests para funciones de cifrado."""

    @patch('app.services.document_vault.boto3')
    @patch('app.services.document_vault.settings')
    def test_derive_key(self, mock_settings, mock_boto3):
        """Test derivacion de clave de cifrado."""
        mock_settings.AWS_ACCESS_KEY_ID = None
        mock_settings.ENCRYPTION_KEY = "test-encryption-key-32chars!!"

        vault = DocumentVault()
        assert vault._encryption_key is not None
        assert len(vault._encryption_key) > 0

    @patch('app.services.document_vault.boto3')
    @patch('app.services.document_vault.settings')
    def test_cifrar_descifrar_roundtrip(self, mock_settings, mock_boto3):
        """Test cifrado y descifrado."""
        mock_settings.AWS_ACCESS_KEY_ID = None
        mock_settings.ENCRYPTION_KEY = "test-encryption-key-32chars!!"

        vault = DocumentVault()
        contenido_original = b"Este es un documento de prueba"

        # Cifrar
        contenido_cifrado = vault._cifrar_archivo(contenido_original)
        assert contenido_cifrado != contenido_original

        # Descifrar
        contenido_descifrado = vault._descifrar_archivo(contenido_cifrado)
        assert contenido_descifrado == contenido_original


class TestDocumentVaultHash:
    """Tests para calculo de hash."""

    @patch('app.services.document_vault.boto3')
    @patch('app.services.document_vault.settings')
    def test_calcular_hash(self, mock_settings, mock_boto3):
        """Test calculo de SHA-256."""
        mock_settings.AWS_ACCESS_KEY_ID = None
        mock_settings.ENCRYPTION_KEY = "test-encryption-key-32chars!!"

        vault = DocumentVault()
        contenido = b"contenido de prueba"

        hash_result = vault._calcular_hash(contenido)

        assert len(hash_result) == 64  # SHA-256 produce 64 caracteres hex
        assert hash_result.isalnum()

    @patch('app.services.document_vault.boto3')
    @patch('app.services.document_vault.settings')
    def test_hash_deterministic(self, mock_settings, mock_boto3):
        """Test que el hash es deterministico."""
        mock_settings.AWS_ACCESS_KEY_ID = None
        mock_settings.ENCRYPTION_KEY = "test-encryption-key-32chars!!"

        vault = DocumentVault()
        contenido = b"mismo contenido"

        hash1 = vault._calcular_hash(contenido)
        hash2 = vault._calcular_hash(contenido)

        assert hash1 == hash2

    @patch('app.services.document_vault.boto3')
    @patch('app.services.document_vault.settings')
    def test_hash_different_content(self, mock_settings, mock_boto3):
        """Test que contenido diferente produce hash diferente."""
        mock_settings.AWS_ACCESS_KEY_ID = None
        mock_settings.ENCRYPTION_KEY = "test-encryption-key-32chars!!"

        vault = DocumentVault()

        hash1 = vault._calcular_hash(b"contenido 1")
        hash2 = vault._calcular_hash(b"contenido 2")

        assert hash1 != hash2


class TestDocumentVaultS3Key:
    """Tests para generacion de S3 key."""

    @patch('app.services.document_vault.boto3')
    @patch('app.services.document_vault.settings')
    def test_generar_s3_key_format(self, mock_settings, mock_boto3):
        """Test formato de S3 key."""
        mock_settings.AWS_ACCESS_KEY_ID = None
        mock_settings.ENCRYPTION_KEY = "test-encryption-key-32chars!!"

        vault = DocumentVault()
        s3_key = vault._generar_s3_key(
            user_id="user-123",
            tipo_documento="ine",
            extension=".pdf"
        )

        assert "user-123" in s3_key
        assert "ine" in s3_key
        assert s3_key.endswith(".pdf")

    @patch('app.services.document_vault.boto3')
    @patch('app.services.document_vault.settings')
    def test_generar_s3_key_unique(self, mock_settings, mock_boto3):
        """Test que cada key es unica."""
        mock_settings.AWS_ACCESS_KEY_ID = None
        mock_settings.ENCRYPTION_KEY = "test-encryption-key-32chars!!"

        vault = DocumentVault()

        key1 = vault._generar_s3_key("user-1", "ine", ".pdf")
        key2 = vault._generar_s3_key("user-1", "ine", ".pdf")

        # Deberian ser diferentes por UUID
        assert key1 != key2
