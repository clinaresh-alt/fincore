"""
Modelos para gestión de API Keys.
Sistema de autenticación programática para integraciones.
"""
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey,
    Text, Enum as SQLEnum, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
import secrets
import hashlib

from app.core.database import Base


class APIKeyStatus(str, enum.Enum):
    """Estado de la API Key."""
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class APIKeyPermission(str, enum.Enum):
    """Permisos disponibles para API Keys."""
    # Lectura
    READ_PORTFOLIO = "read:portfolio"
    READ_TRANSACTIONS = "read:transactions"
    READ_BALANCES = "read:balances"
    READ_MARKET = "read:market"

    # Trading
    TRADE_SPOT = "trade:spot"
    TRADE_CREATE_ORDER = "trade:create_order"
    TRADE_CANCEL_ORDER = "trade:cancel_order"

    # Wallet
    WALLET_DEPOSIT = "wallet:deposit"
    WALLET_WITHDRAW = "wallet:withdraw"
    WALLET_TRANSFER = "wallet:transfer"

    # Remesas
    REMITTANCE_CREATE = "remittance:create"
    REMITTANCE_READ = "remittance:read"

    # Admin (solo para admins)
    ADMIN_FULL = "admin:full"


class APIKey(Base):
    """
    API Key para acceso programático.
    Permite a usuarios y sistemas externos interactuar con la API.
    """
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )

    # Identificación
    name = Column(String(100), nullable=False)  # "Trading Bot", "Mobile App"
    description = Column(Text, nullable=True)

    # Key (solo se muestra una vez al crear)
    # Guardamos el hash, no la key en texto plano
    key_prefix = Column(String(8), nullable=False)  # Primeros 8 chars para identificación
    key_hash = Column(String(64), nullable=False, unique=True)  # SHA-256 del key completo

    # Permisos
    permissions = Column(ARRAY(String), default=[])  # Lista de permisos

    # Restricciones
    allowed_ips = Column(ARRAY(String), nullable=True)  # IPs permitidas (null = todas)
    allowed_origins = Column(ARRAY(String), nullable=True)  # Origins CORS permitidos

    # Límites de rate
    rate_limit_per_minute = Column(Integer, default=60)
    rate_limit_per_day = Column(Integer, default=10000)

    # Estado
    status = Column(
        SQLEnum(APIKeyStatus, name="api_key_status_enum", create_type=False),
        default=APIKeyStatus.ACTIVE
    )

    # Expiración
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Null = no expira

    # Uso
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_used_ip = Column(String(45), nullable=True)
    total_requests = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    user = relationship("User", backref="api_keys")
    logs = relationship("APIKeyLog", back_populates="api_key", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_api_key_user", "user_id"),
        Index("idx_api_key_hash", "key_hash"),
        Index("idx_api_key_prefix", "key_prefix"),
        Index("idx_api_key_status", "status"),
    )

    @staticmethod
    def generate_key() -> tuple[str, str, str]:
        """
        Genera una nueva API key.
        Returns: (full_key, prefix, hash)
        """
        # Formato: fck_live_XXXX...XXXX (32 chars random)
        random_part = secrets.token_hex(16)  # 32 caracteres hex
        full_key = f"fck_live_{random_part}"
        prefix = full_key[:8]
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        return full_key, prefix, key_hash

    @staticmethod
    def hash_key(key: str) -> str:
        """Hash de una API key."""
        return hashlib.sha256(key.encode()).hexdigest()

    def has_permission(self, permission: str) -> bool:
        """Verifica si tiene un permiso específico."""
        if APIKeyPermission.ADMIN_FULL.value in self.permissions:
            return True
        return permission in self.permissions

    def is_valid(self) -> bool:
        """Verifica si la key es válida (activa y no expirada)."""
        if self.status != APIKeyStatus.ACTIVE:
            return False
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
        return True

    def is_ip_allowed(self, ip: str) -> bool:
        """Verifica si la IP está permitida."""
        if not self.allowed_ips:
            return True
        return ip in self.allowed_ips


class APIKeyLog(Base):
    """
    Log de uso de API Keys.
    Registro de todas las solicitudes realizadas.
    """
    __tablename__ = "api_key_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False
    )

    # Request info
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)  # GET, POST, etc.
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Response
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)  # Tiempo de respuesta en ms

    # Error (si hubo)
    error_message = Column(Text, nullable=True)

    # Metadata
    request_id = Column(String(36), nullable=True)  # UUID de la request
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    api_key = relationship("APIKey", back_populates="logs")

    __table_args__ = (
        Index("idx_api_log_key", "api_key_id"),
        Index("idx_api_log_created", "created_at"),
        Index("idx_api_log_endpoint", "endpoint"),
    )


class APIRateLimit(Base):
    """
    Tracking de rate limits por API Key.
    Usa ventana deslizante para control.
    """
    __tablename__ = "api_rate_limits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False
    )

    # Contadores
    window_type = Column(String(10), nullable=False)  # "minute" or "day"
    window_start = Column(DateTime(timezone=True), nullable=False)
    request_count = Column(Integer, default=0)

    __table_args__ = (
        Index("idx_rate_limit_key_window", "api_key_id", "window_type", "window_start"),
    )
