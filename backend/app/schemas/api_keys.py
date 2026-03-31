"""
Schemas Pydantic para API Keys.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field


class APIKeyPermissionEnum(str, Enum):
    """Permisos disponibles."""
    READ_PORTFOLIO = "read:portfolio"
    READ_TRANSACTIONS = "read:transactions"
    READ_BALANCES = "read:balances"
    READ_MARKET = "read:market"
    TRADE_SPOT = "trade:spot"
    TRADE_CREATE_ORDER = "trade:create_order"
    TRADE_CANCEL_ORDER = "trade:cancel_order"
    WALLET_DEPOSIT = "wallet:deposit"
    WALLET_WITHDRAW = "wallet:withdraw"
    WALLET_TRANSFER = "wallet:transfer"
    REMITTANCE_CREATE = "remittance:create"
    REMITTANCE_READ = "remittance:read"


class APIKeyCreate(BaseModel):
    """Crear API Key."""
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = None
    permissions: List[str] = Field(default=["read:portfolio", "read:balances"])
    allowed_ips: Optional[List[str]] = None
    expires_at: Optional[datetime] = None
    rate_limit_per_minute: int = Field(default=60, ge=1, le=1000)
    rate_limit_per_day: int = Field(default=10000, ge=100, le=100000)


class APIKeyResponse(BaseModel):
    """Respuesta de API Key (sin el key completo)."""
    id: UUID
    name: str
    description: Optional[str]
    key_prefix: str
    permissions: List[str]
    allowed_ips: Optional[List[str]]
    status: str
    expires_at: Optional[datetime]
    rate_limit_per_minute: int
    rate_limit_per_day: int
    last_used_at: Optional[datetime]
    last_used_ip: Optional[str]
    total_requests: int
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyCreatedResponse(BaseModel):
    """Respuesta al crear API Key (incluye el key completo UNA SOLA VEZ)."""
    id: UUID
    name: str
    key: str  # Solo se muestra esta única vez
    key_prefix: str
    permissions: List[str]
    expires_at: Optional[datetime]
    created_at: datetime
    warning: str = "Guarda esta API Key de forma segura. No se mostrará de nuevo."


class APIKeyUpdate(BaseModel):
    """Actualizar API Key."""
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    allowed_ips: Optional[List[str]] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=1000)
    rate_limit_per_day: Optional[int] = Field(None, ge=100, le=100000)


class APIKeyLogEntry(BaseModel):
    """Entrada de log de API Key."""
    id: UUID
    endpoint: str
    method: str
    ip_address: Optional[str]
    status_code: Optional[int]
    response_time_ms: Optional[int]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyLogsResponse(BaseModel):
    """Respuesta de logs."""
    logs: List[APIKeyLogEntry]
    total: int
    page: int
    page_size: int


class APIKeyStatsResponse(BaseModel):
    """Estadísticas de uso de API Key."""
    api_key_id: UUID
    total_requests: int
    requests_today: int
    requests_this_month: int
    avg_response_time_ms: float
    error_rate: float
    top_endpoints: List[dict]
    requests_by_day: List[dict]


class RateLimitInfo(BaseModel):
    """Información de rate limit."""
    limit_per_minute: int
    remaining_per_minute: int
    limit_per_day: int
    remaining_per_day: int
    reset_minute: datetime
    reset_day: datetime
