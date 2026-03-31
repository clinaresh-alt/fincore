"""
Modelos para Sistema de Soporte.
Tickets, chat en vivo, y status page.
"""
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey,
    Text, Enum as SQLEnum, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base


class TicketCategory(str, enum.Enum):
    """Categorías de tickets."""
    GENERAL = "general"
    ACCOUNT = "account"
    TRADING = "trading"
    WALLET = "wallet"
    REMITTANCE = "remittance"
    KYC = "kyc"
    TECHNICAL = "technical"
    BILLING = "billing"
    SECURITY = "security"
    COMPLIANCE = "compliance"


class TicketPriority(str, enum.Enum):
    """Prioridad del ticket."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(str, enum.Enum):
    """Estado del ticket."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_USER = "waiting_user"
    WAITING_THIRD_PARTY = "waiting_third_party"
    RESOLVED = "resolved"
    CLOSED = "closed"


class SupportTicket(Base):
    """
    Ticket de soporte.
    Sistema de tickets para gestión de solicitudes de usuarios.
    """
    __tablename__ = "support_tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_number = Column(String(20), unique=True, nullable=False)  # FCK-2024-00001
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    # Información del ticket
    subject = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(
        SQLEnum(TicketCategory, name="ticket_category_enum", create_type=False),
        default=TicketCategory.GENERAL
    )
    priority = Column(
        SQLEnum(TicketPriority, name="ticket_priority_enum", create_type=False),
        default=TicketPriority.MEDIUM
    )
    status = Column(
        SQLEnum(TicketStatus, name="ticket_status_enum", create_type=False),
        default=TicketStatus.OPEN
    )

    # Asignación
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    # Datos del usuario (para tickets anónimos o externos)
    user_email = Column(String(255), nullable=True)
    user_name = Column(String(100), nullable=True)

    # Metadata
    tags = Column(JSONB, default=[])
    attachments = Column(JSONB, default=[])  # [{filename, url, size, type}]

    # Relacionado a
    related_entity_type = Column(String(50), nullable=True)  # "remittance", "order", etc.
    related_entity_id = Column(UUID(as_uuid=True), nullable=True)

    # Satisfacción
    satisfaction_rating = Column(Integer, nullable=True)  # 1-5
    satisfaction_feedback = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    first_response_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    user = relationship("User", foreign_keys=[user_id], backref="support_tickets")
    agent = relationship("User", foreign_keys=[assigned_to], backref="assigned_tickets")
    messages = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_ticket_user", "user_id"),
        Index("idx_ticket_status", "status"),
        Index("idx_ticket_priority", "priority"),
        Index("idx_ticket_category", "category"),
        Index("idx_ticket_number", "ticket_number"),
        Index("idx_ticket_created", "created_at"),
    )

    @staticmethod
    def generate_ticket_number(db) -> str:
        """Generar número de ticket único."""
        year = datetime.utcnow().year
        # Obtener último número del año
        from sqlalchemy import func
        last_ticket = db.query(func.max(SupportTicket.ticket_number)).filter(
            SupportTicket.ticket_number.like(f"FCK-{year}-%")
        ).scalar()

        if last_ticket:
            last_num = int(last_ticket.split("-")[-1])
            new_num = last_num + 1
        else:
            new_num = 1

        return f"FCK-{year}-{new_num:05d}"


class TicketMessage(Base):
    """
    Mensaje en un ticket.
    Comunicación entre usuario y soporte.
    """
    __tablename__ = "ticket_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(
        UUID(as_uuid=True),
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    # Mensaje
    message = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False)  # Notas internas (no visibles al usuario)
    is_from_user = Column(Boolean, default=True)  # True = usuario, False = agente

    # Attachments
    attachments = Column(JSONB, default=[])

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    ticket = relationship("SupportTicket", back_populates="messages")
    user = relationship("User", backref="ticket_messages")

    __table_args__ = (
        Index("idx_message_ticket", "ticket_id"),
        Index("idx_message_created", "created_at"),
    )


class SystemStatus(str, enum.Enum):
    """Estado del sistema."""
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    MAINTENANCE = "maintenance"


class StatusComponent(Base):
    """
    Componente del sistema para status page.
    """
    __tablename__ = "status_components"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Información
    name = Column(String(100), nullable=False)  # "API", "Web App", "Wallet Service"
    description = Column(Text, nullable=True)
    group = Column(String(50), nullable=True)  # "Core", "Integrations", "Infrastructure"

    # Estado actual
    status = Column(
        SQLEnum(SystemStatus, name="system_status_enum", create_type=False),
        default=SystemStatus.OPERATIONAL
    )

    # Orden de visualización
    display_order = Column(Integer, default=0)
    is_visible = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    last_incident_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    incidents = relationship("StatusIncident", back_populates="component")

    __table_args__ = (
        Index("idx_component_status", "status"),
        Index("idx_component_order", "display_order"),
    )


class StatusIncident(Base):
    """
    Incidente de status.
    """
    __tablename__ = "status_incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    component_id = Column(
        UUID(as_uuid=True),
        ForeignKey("status_components.id", ondelete="CASCADE"),
        nullable=True
    )

    # Información
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        SQLEnum(SystemStatus, name="system_status_enum", create_type=False),
        nullable=False
    )

    # Tipo
    is_scheduled = Column(Boolean, default=False)  # Mantenimiento programado
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    scheduled_until = Column(DateTime(timezone=True), nullable=True)

    # Estado del incidente
    is_resolved = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    component = relationship("StatusComponent", back_populates="incidents")
    updates = relationship("StatusUpdate", back_populates="incident", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_incident_created", "created_at"),
        Index("idx_incident_resolved", "is_resolved"),
    )


class StatusUpdate(Base):
    """
    Actualización de un incidente.
    """
    __tablename__ = "status_updates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("status_incidents.id", ondelete="CASCADE"),
        nullable=False
    )

    # Información
    message = Column(Text, nullable=False)
    status = Column(
        SQLEnum(SystemStatus, name="system_status_enum", create_type=False),
        nullable=False
    )

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    incident = relationship("StatusIncident", back_populates="updates")

    __table_args__ = (
        Index("idx_update_incident", "incident_id"),
        Index("idx_update_created", "created_at"),
    )
