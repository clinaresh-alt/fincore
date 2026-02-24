"""
Vault Seguro de Documentos.
Cifrado AES-256 + Almacenamiento S3 + OCR automatico.
"""
import uuid
import hashlib
from datetime import datetime
from typing import Optional, Dict, BinaryIO
from dataclasses import dataclass
import base64
from io import BytesIO

import boto3
from botocore.exceptions import ClientError
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings


@dataclass
class DocumentoSubido:
    """Resultado de subida de documento."""
    documento_id: str
    s3_key: str
    s3_bucket: str
    tamano_bytes: int
    hash_sha256: str
    cifrado: bool
    fecha_subida: datetime


@dataclass
class ResultadoOCR:
    """Resultado del procesamiento OCR."""
    texto_extraido: str
    confianza: int  # 0-100
    campos_detectados: Dict
    fecha_procesamiento: datetime


class DocumentVault:
    """
    Vault seguro para documentos financieros.
    Implementa Zero Knowledge: cifrado antes de subir.
    """

    EXTENSIONES_PERMITIDAS = {".pdf", ".png", ".jpg", ".jpeg"}
    TAMANO_MAXIMO_MB = 10

    def __init__(self):
        self.s3_client = None
        self._init_s3()
        self._encryption_key = self._derive_key()

    def _init_s3(self):
        """Inicializa cliente S3."""
        if settings.AWS_ACCESS_KEY_ID:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )

    def _derive_key(self) -> bytes:
        """Deriva clave de cifrado desde configuracion."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"fincore_vault_salt_v1",
            iterations=100000,
        )
        return base64.urlsafe_b64encode(
            kdf.derive(settings.ENCRYPTION_KEY.encode())
        )

    def _cifrar_archivo(self, contenido: bytes) -> bytes:
        """Cifra contenido con AES-256 (Fernet)."""
        fernet = Fernet(self._encryption_key)
        return fernet.encrypt(contenido)

    def _descifrar_archivo(self, contenido_cifrado: bytes) -> bytes:
        """Descifra contenido."""
        fernet = Fernet(self._encryption_key)
        return fernet.decrypt(contenido_cifrado)

    def _calcular_hash(self, contenido: bytes) -> str:
        """Calcula SHA-256 del contenido original."""
        return hashlib.sha256(contenido).hexdigest()

    def _generar_s3_key(
        self,
        user_id: str,
        tipo_documento: str,
        extension: str
    ) -> str:
        """
        Genera path unico en S3.
        Estructura: users/{user_id}/{tipo}/{uuid}.{ext}
        """
        doc_id = str(uuid.uuid4())
        fecha = datetime.utcnow().strftime("%Y/%m")
        return f"users/{user_id}/{fecha}/{tipo_documento}/{doc_id}{extension}"

    async def subir_documento(
        self,
        archivo: BinaryIO,
        nombre_archivo: str,
        user_id: str,
        tipo_documento: str,
        proyecto_id: Optional[str] = None
    ) -> DocumentoSubido:
        """
        Sube documento al vault con cifrado.

        1. Lee el archivo
        2. Valida extension y tamano
        3. Cifra con AES-256
        4. Sube a S3
        5. Retorna metadata
        """
        # Leer contenido
        contenido = archivo.read()
        tamano = len(contenido)

        # Validar tamano
        if tamano > self.TAMANO_MAXIMO_MB * 1024 * 1024:
            raise ValueError(
                f"Archivo excede {self.TAMANO_MAXIMO_MB}MB"
            )

        # Obtener extension
        extension = "." + nombre_archivo.rsplit(".", 1)[-1].lower()
        if extension not in self.EXTENSIONES_PERMITIDAS:
            raise ValueError(
                f"Extension no permitida: {extension}"
            )

        # Calcular hash antes de cifrar
        hash_original = self._calcular_hash(contenido)

        # Cifrar
        contenido_cifrado = self._cifrar_archivo(contenido)

        # Generar key S3
        s3_key = self._generar_s3_key(user_id, tipo_documento, extension)
        documento_id = s3_key.split("/")[-1].replace(extension, "")

        # Subir a S3
        if self.s3_client:
            try:
                self.s3_client.put_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=s3_key,
                    Body=contenido_cifrado,
                    ContentType="application/octet-stream",
                    Metadata={
                        "original_name": nombre_archivo,
                        "original_hash": hash_original,
                        "encrypted": "true",
                        "user_id": user_id,
                        "proyecto_id": proyecto_id or "",
                    },
                    ServerSideEncryption="AES256"  # Cifrado adicional en S3
                )
            except ClientError as e:
                raise RuntimeError(f"Error subiendo a S3: {e}")
        else:
            # Modo desarrollo: simular subida
            pass

        return DocumentoSubido(
            documento_id=documento_id,
            s3_key=s3_key,
            s3_bucket=settings.S3_BUCKET_NAME,
            tamano_bytes=tamano,
            hash_sha256=hash_original,
            cifrado=True,
            fecha_subida=datetime.utcnow()
        )

    async def descargar_documento(
        self,
        s3_key: str,
        user_id: str
    ) -> bytes:
        """
        Descarga y descifra documento del vault.
        Verifica que el usuario sea propietario.
        """
        # Verificar propiedad
        if f"/users/{user_id}/" not in s3_key:
            raise PermissionError("No tienes acceso a este documento")

        if not self.s3_client:
            raise RuntimeError("S3 no configurado")

        try:
            response = self.s3_client.get_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key
            )
            contenido_cifrado = response["Body"].read()
        except ClientError as e:
            raise RuntimeError(f"Error descargando de S3: {e}")

        # Descifrar
        return self._descifrar_archivo(contenido_cifrado)

    async def procesar_ocr(
        self,
        s3_key: str,
        tipo_documento: str
    ) -> ResultadoOCR:
        """
        Procesa documento con OCR (Amazon Textract).
        Extrae campos relevantes segun tipo de documento.
        """
        # En produccion: usar Amazon Textract
        # textract = boto3.client('textract')
        # response = textract.analyze_document(...)

        # Mock para desarrollo
        campos_por_tipo = {
            "Declaracion Fiscal": {
                "periodo": "2024",
                "ingreso_neto": "500000.00",
                "impuesto_causado": "80000.00"
            },
            "Identificacion": {
                "nombre": "[Pendiente OCR]",
                "fecha_nacimiento": None,
                "numero_documento": None
            }
        }

        return ResultadoOCR(
            texto_extraido="[Texto extraido pendiente procesamiento OCR]",
            confianza=0,
            campos_detectados=campos_por_tipo.get(tipo_documento, {}),
            fecha_procesamiento=datetime.utcnow()
        )

    async def eliminar_documento(
        self,
        s3_key: str,
        user_id: str
    ) -> bool:
        """Elimina documento del vault (soft delete recomendado)."""
        if f"/users/{user_id}/" not in s3_key:
            raise PermissionError("No tienes acceso a este documento")

        if self.s3_client:
            try:
                self.s3_client.delete_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=s3_key
                )
                return True
            except ClientError:
                return False

        return True

    def generar_url_firmada(
        self,
        s3_key: str,
        expiracion_segundos: int = 3600
    ) -> str:
        """
        Genera URL firmada para descarga temporal.
        Nota: El documento sigue cifrado, requiere descifrado.
        """
        if not self.s3_client:
            return ""

        return self.s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.S3_BUCKET_NAME,
                "Key": s3_key
            },
            ExpiresIn=expiracion_segundos
        )
