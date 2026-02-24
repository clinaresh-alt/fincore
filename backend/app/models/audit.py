"""
Audit Trail - Log inmutable para compliance.
Registra cada accion del sistema para cumplimiento legal.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Text, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Index
import enum

from app.core.database import Base


class AuditAction(str, enum.Enum):
    """Acciones auditables del sistema."""
    # Auth
    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    MFA_ENABLED = "MFA_ENABLED"
    MFA_VERIFIED = "MFA_VERIFIED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"

    # Usuarios
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    KYC_VERIFIED = "KYC_VERIFIED"
    TAX_VALIDATED = "TAX_VALIDATED"

    # Proyectos
    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_EVALUATED = "PROJECT_EVALUATED"
    PROJECT_APPROVED = "PROJECT_APPROVED"
    PROJECT_REJECTED = "PROJECT_REJECTED"

    # Inversiones
    INVESTMENT_CREATED = "INVESTMENT_CREATED"
    INVESTMENT_CONFIRMED = "INVESTMENT_CONFIRMED"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    RETURN_PAID = "RETURN_PAID"

    # Documentos
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_REVIEWED = "DOCUMENT_REVIEWED"
    DOCUMENT_DOWNLOADED = "DOCUMENT_DOWNLOADED"

    # Sistema
    CONFIG_CHANGED = "CONFIG_CHANGED"
    ROLE_CHANGED = "ROLE_CHANGED"


class AuditLog(Base):
    """
    Log de auditoria inmutable.
    No se pueden eliminar ni modificar registros.
    """
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Usuario que realizo la accion
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True  # Puede ser null para acciones del sistema
    )

    # Accion realizada
    action = Column(
        SQLEnum(AuditAction, name="audit_action_enum"),
        nullable=False
    )

    # Recurso afectado
    resource_type = Column(String(50), nullable=True)  # User, Project, Investment, etc.
    resource_id = Column(UUID(as_uuid=True), nullable=True)

    # Detalles de la accion
    description = Column(Text, nullable=True)
    old_values = Column(JSONB, nullable=True)  # Estado anterior
    new_values = Column(JSONB, nullable=True)  # Estado nuevo

    # Contexto de la request
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    endpoint = Column(String(255), nullable=True)
    method = Column(String(10), nullable=True)  # GET, POST, etc.

    # Resultado
    success = Column(String(10), default="success")  # success, failure, error
    error_message = Column(Text, nullable=True)

    # Timestamp inmutable
    timestamp = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    # Relaciones
    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )

    def __repr__(self):
        return f"<AuditLog {self.action} by {self.user_id}>"
