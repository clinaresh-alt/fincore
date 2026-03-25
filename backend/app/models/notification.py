"""
Modelo de Notificaciones.
Almacena notificaciones para usuarios con persistencia.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class NotificationType(str, enum.Enum):
    """Tipos de notificacion."""
    # Auditoria
    AUDIT_STARTED = "audit_started"
    AUDIT_COMPLETED = "audit_completed"
    AUDIT_FAILED = "audit_failed"
    AUDIT_FINDING = "audit_finding"

    # Compliance
    COMPLIANCE_ALERT = "compliance_alert"
    KYC_STATUS_CHANGE = "kyc_status_change"
    RISK_ALERT = "risk_alert"

    # Inversiones
    INVESTMENT_RECEIVED = "investment_received"
    INVESTMENT_CONFIRMED = "investment_confirmed"
    DIVIDEND_AVAILABLE = "dividend_available"

    # Proyectos
    PROJECT_STATUS_CHANGE = "project_status_change"
    PROJECT_MILESTONE = "project_milestone"

    # Sistema
    SYSTEM_ALERT = "system_alert"
    SYSTEM_MAINTENANCE = "system_maintenance"

    # General
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class NotificationPriority(str, enum.Enum):
    """Prioridad de notificacion."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Notification(Base):
    """
    Tabla de notificaciones.
    Almacena notificaciones enviadas a usuarios.
    """
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Usuario destinatario
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Contenido
    notification_type = Column(
        SQLEnum(NotificationType, name="notification_type_enum"),
        nullable=False
    )
    priority = Column(
        SQLEnum(NotificationPriority, name="notification_priority_enum"),
        default=NotificationPriority.MEDIUM,
        nullable=False
    )
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)

    # Datos adicionales (JSON)
    data = Column(JSONB, nullable=True)

    # Estado
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Entrega WebSocket
    delivered_via_ws = Column(Boolean, default=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    user = relationship("User", back_populates="notifications")

    # Indices para consultas frecuentes
    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "is_read"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_type", "notification_type"),
    )

    def __repr__(self):
        return f"<Notification {self.id}: {self.title}>"

    def to_dict(self):
        """Convierte a diccionario para API."""
        return {
            "id": str(self.id),
            "notification_type": self.notification_type.value,
            "priority": self.priority.value,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class NotificationPreference(Base):
    """
    Preferencias de notificaciones por usuario.
    Permite configurar que notificaciones recibir.
    """
    __tablename__ = "notification_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Preferencias por tipo
    audit_notifications = Column(Boolean, default=True)
    compliance_notifications = Column(Boolean, default=True)
    investment_notifications = Column(Boolean, default=True)
    project_notifications = Column(Boolean, default=True)
    system_notifications = Column(Boolean, default=True)

    # Preferencias por prioridad minima
    min_priority = Column(
        SQLEnum(NotificationPriority, name="notification_priority_pref_enum"),
        default=NotificationPriority.LOW
    )

    # Canales
    enable_websocket = Column(Boolean, default=True)
    enable_email = Column(Boolean, default=False)

    # Horarios (opcional)
    quiet_hours_start = Column(String(5), nullable=True)  # HH:MM
    quiet_hours_end = Column(String(5), nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacion
    user = relationship("User", back_populates="notification_preferences")

    def __repr__(self):
        return f"<NotificationPreference user={self.user_id}>"
