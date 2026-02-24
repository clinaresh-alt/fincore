"""
Modelo de Documentos - Vault Seguro.
Almacenamiento cifrado con OCR automatico.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime,
    Text, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Index
import enum

from app.core.database import Base


class DocumentType(str, enum.Enum):
    """Tipos de documento requeridos para KYC."""
    IDENTIFICACION = "Identificacion"           # INE, Pasaporte
    COMPROBANTE_DOMICILIO = "Comprobante Domicilio"
    DECLARACION_FISCAL = "Declaracion Fiscal"   # Ultimos 2 anos
    ACTA_CONSTITUTIVA = "Acta Constitutiva"     # Personas juridicas
    PODER_NOTARIAL = "Poder Notarial"
    ESTADOS_FINANCIEROS = "Estados Financieros"
    CONTRATO_FIRMADO = "Contrato Firmado"
    OTRO = "Otro"


class DocumentStatus(str, enum.Enum):
    """Estados del documento."""
    PENDIENTE = "Pendiente"      # Subido, esperando revision
    EN_REVISION = "En Revision"  # Analista revisando
    APROBADO = "Aprobado"
    RECHAZADO = "Rechazado"
    EXPIRADO = "Expirado"


class Document(Base):
    """
    Documentos del vault seguro.
    Cifrados con AES-256 antes de subir a S3.
    """
    __tablename__ = "documentos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Propietario
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )

    # Proyecto relacionado (opcional)
    proyecto_id = Column(
        UUID(as_uuid=True),
        ForeignKey("proyectos.id", ondelete="SET NULL"),
        nullable=True
    )

    # Metadata del documento
    tipo = Column(
        SQLEnum(DocumentType, name="document_type_enum"),
        nullable=False
    )
    nombre_archivo = Column(String(255), nullable=False)
    nombre_original = Column(String(255), nullable=False)
    extension = Column(String(10), nullable=False)
    mime_type = Column(String(100), nullable=False)
    tamano_bytes = Column(Integer, nullable=False)

    # Almacenamiento S3
    s3_bucket = Column(String(100), nullable=False)
    s3_key = Column(Text, nullable=False)  # Path en S3 (cifrado)
    s3_version_id = Column(String(100), nullable=True)

    # Cifrado
    cifrado = Column(Boolean, default=True)
    algoritmo_cifrado = Column(String(20), default="AES-256")

    # OCR y extraccion
    ocr_procesado = Column(Boolean, default=False)
    ocr_resultado = Column(JSONB, nullable=True)  # Datos extraidos
    ocr_confianza = Column(Integer, nullable=True)  # 0-100

    # Estado y revision
    estado = Column(
        SQLEnum(DocumentStatus, name="document_status_enum"),
        default=DocumentStatus.PENDIENTE
    )
    revisado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    fecha_revision = Column(DateTime(timezone=True), nullable=True)
    motivo_rechazo = Column(Text, nullable=True)

    # Vigencia
    fecha_emision = Column(DateTime(timezone=True), nullable=True)
    fecha_vencimiento = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    # Relaciones
    user = relationship("User", back_populates="documents", foreign_keys=[user_id])

    __table_args__ = (
        Index("idx_documento_usuario", "user_id"),
        Index("idx_documento_tipo", "tipo"),
        Index("idx_documento_estado", "estado"),
    )

    def __repr__(self):
        return f"<Document {self.nombre_original} ({self.tipo})>"
