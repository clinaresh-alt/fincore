"""
Schemas Pydantic para Sistema de Soporte.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, EmailStr


# ==================== ENUMS ====================

class TicketCategoryEnum(str, Enum):
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


class TicketPriorityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatusEnum(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_USER = "waiting_user"
    WAITING_THIRD_PARTY = "waiting_third_party"
    RESOLVED = "resolved"
    CLOSED = "closed"


class SystemStatusEnum(str, Enum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    MAINTENANCE = "maintenance"


# ==================== TICKET SCHEMAS ====================

class TicketCreate(BaseModel):
    """Crear ticket de soporte."""
    subject: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=20)
    category: TicketCategoryEnum = TicketCategoryEnum.GENERAL
    priority: TicketPriorityEnum = TicketPriorityEnum.MEDIUM
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[UUID] = None
    attachments: Optional[List[dict]] = None


class TicketMessageCreate(BaseModel):
    """Crear mensaje en ticket."""
    message: str = Field(..., min_length=1)
    attachments: Optional[List[dict]] = None


class TicketMessageResponse(BaseModel):
    """Respuesta de mensaje."""
    id: UUID
    ticket_id: UUID
    user_id: Optional[UUID]
    message: str
    is_internal: bool
    is_from_user: bool
    attachments: List[dict]
    created_at: datetime
    read_at: Optional[datetime]

    class Config:
        from_attributes = True


class TicketResponse(BaseModel):
    """Respuesta de ticket."""
    id: UUID
    ticket_number: str
    user_id: Optional[UUID]
    subject: str
    description: str
    category: str
    priority: str
    status: str
    assigned_to: Optional[UUID]
    user_email: Optional[str]
    user_name: Optional[str]
    tags: List[str]
    attachments: List[dict]
    related_entity_type: Optional[str]
    related_entity_id: Optional[UUID]
    satisfaction_rating: Optional[int]
    created_at: datetime
    updated_at: datetime
    first_response_at: Optional[datetime]
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TicketDetailResponse(BaseModel):
    """Respuesta detallada de ticket con mensajes."""
    ticket: TicketResponse
    messages: List[TicketMessageResponse]


class TicketListResponse(BaseModel):
    """Lista de tickets."""
    tickets: List[TicketResponse]
    total: int
    page: int
    page_size: int


class TicketRateRequest(BaseModel):
    """Calificar resolución del ticket."""
    rating: int = Field(..., ge=1, le=5)
    feedback: Optional[str] = None


# ==================== STATUS PAGE SCHEMAS ====================

class StatusComponentResponse(BaseModel):
    """Respuesta de componente."""
    id: UUID
    name: str
    description: Optional[str]
    group: Optional[str]
    status: str
    display_order: int
    last_incident_at: Optional[datetime]

    class Config:
        from_attributes = True


class StatusUpdateResponse(BaseModel):
    """Respuesta de actualización de incidente."""
    id: UUID
    message: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class StatusIncidentResponse(BaseModel):
    """Respuesta de incidente."""
    id: UUID
    component_id: Optional[UUID]
    component_name: Optional[str]
    title: str
    description: Optional[str]
    status: str
    is_scheduled: bool
    scheduled_for: Optional[datetime]
    scheduled_until: Optional[datetime]
    is_resolved: bool
    created_at: datetime
    resolved_at: Optional[datetime]
    updates: List[StatusUpdateResponse]

    class Config:
        from_attributes = True


class StatusPageResponse(BaseModel):
    """Respuesta completa de status page."""
    overall_status: str
    components: List[StatusComponentResponse]
    active_incidents: List[StatusIncidentResponse]
    scheduled_maintenances: List[StatusIncidentResponse]
    recent_incidents: List[StatusIncidentResponse]
    last_updated: datetime


# ==================== TAX CENTER SCHEMAS ====================

class TaxYearSummary(BaseModel):
    """Resumen fiscal del año."""
    year: int
    total_investments: float
    total_returns: float
    total_dividends: float
    total_trades: int
    realized_gains: float
    realized_losses: float
    net_realized_pnl: float
    total_fees_paid: float
    total_remittances_sent: float
    total_remittances_received: float


class TaxTransactionItem(BaseModel):
    """Transacción para reporte fiscal."""
    date: datetime
    type: str  # "investment", "dividend", "trade", "remittance"
    description: str
    amount: float
    currency: str
    cost_basis: Optional[float] = None
    gain_loss: Optional[float] = None
    reference_id: str


class TaxReportResponse(BaseModel):
    """Reporte fiscal completo."""
    user_id: UUID
    user_name: str
    user_rfc: Optional[str]
    year: int
    generated_at: datetime
    summary: TaxYearSummary
    transactions: List[TaxTransactionItem]
    download_url: Optional[str] = None


# ==================== SAT 69-B SCHEMAS ====================

class SAT69BCheckRequest(BaseModel):
    """Verificar RFC en lista 69-B del SAT."""
    rfc: str = Field(..., min_length=12, max_length=13)


class SAT69BCheckResponse(BaseModel):
    """Resultado de verificación 69-B."""
    rfc: str
    is_listed: bool
    status: str  # "clean", "listed_definitive", "listed_presumed", "listed_favorable"
    list_type: Optional[str] = None  # "69-B", "69-B Bis"
    publication_date: Optional[datetime] = None
    reason: Optional[str] = None
    checked_at: datetime
    source: str = "SAT"


class SAT69BListEntry(BaseModel):
    """Entrada en lista 69-B."""
    rfc: str
    name: str
    list_type: str
    status: str
    publication_date: datetime
    reason: Optional[str]
