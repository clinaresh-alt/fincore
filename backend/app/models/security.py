"""
Modelos de Seguridad Avanzada para FinCore.

Implementa:
- Whitelist de direcciones de retiro con cuarentena 24h
- Anti-phishing con frase secreta
- Gestión de dispositivos y sesiones
- Historial de contraseñas
- Congelamiento de cuenta
"""
import uuid
import secrets
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    Enum as SQLEnum,
    Integer,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship

from app.core.database import Base


# ============ Enums ============

class WithdrawalAddressType(str, Enum):
    """Tipos de dirección de retiro."""
    CRYPTO_ERC20 = "crypto_erc20"      # Ethereum, Polygon, Arbitrum, Base
    CRYPTO_TRC20 = "crypto_trc20"      # TRON
    BANK_CLABE = "bank_clabe"          # CLABE México
    BANK_IBAN = "bank_iban"            # IBAN internacional
    BANK_ACH = "bank_ach"              # ACH USA


class WhitelistStatus(str, Enum):
    """Estados de dirección en whitelist."""
    PENDING = "pending"        # En cuarentena (24h)
    ACTIVE = "active"          # Activa, puede usarse
    SUSPENDED = "suspended"    # Suspendida temporalmente
    CANCELLED = "cancelled"    # Cancelada por el usuario


class DeviceStatus(str, Enum):
    """Estados de dispositivo."""
    TRUSTED = "trusted"        # Dispositivo confiable
    UNKNOWN = "unknown"        # Nuevo dispositivo
    SUSPICIOUS = "suspicious"  # Marcado como sospechoso
    BLOCKED = "blocked"        # Bloqueado


class AccountFreezeReason(str, Enum):
    """Razones de congelamiento de cuenta."""
    USER_REQUESTED = "user_requested"        # Solicitado por usuario
    SUSPICIOUS_ACTIVITY = "suspicious"       # Actividad sospechosa
    COMPLIANCE_HOLD = "compliance"           # Retención de compliance
    FRAUD_DETECTED = "fraud"                 # Fraude detectado
    MULTIPLE_FAILED_LOGIN = "failed_login"   # Múltiples intentos fallidos


# ============ Modelos ============

class WithdrawalWhitelist(Base):
    """
    Whitelist de direcciones de retiro.

    Implementa el patrón de seguridad de Binance:
    - Nueva dirección entra en cuarentena 24h
    - Notificación push + email + SMS
    - Link de cancelación válido durante cuarentena
    - Solo después de 24h se puede usar para retiros
    """
    __tablename__ = "withdrawal_whitelist"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Usuario propietario
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Tipo de dirección
    address_type = Column(
        SQLEnum(WithdrawalAddressType, name="withdrawal_address_type_enum", create_type=False),
        nullable=False
    )

    # Dirección (crypto o bancaria)
    address = Column(String(255), nullable=False)
    address_hash = Column(String(64), nullable=False, index=True)  # SHA256 para búsqueda

    # Metadata adicional según tipo
    # Crypto: network, token_symbol
    # Bank: bank_name, holder_name, swift_code
    metadata = Column(JSONB, default={})

    # Etiqueta del usuario
    label = Column(String(100), nullable=True)

    # Estado y cuarentena
    status = Column(
        SQLEnum(WhitelistStatus, name="whitelist_status_enum", create_type=False),
        default=WhitelistStatus.PENDING,
        nullable=False
    )

    # Cuarentena 24h
    quarantine_ends_at = Column(DateTime(timezone=True), nullable=False)

    # Token de cancelación (válido durante cuarentena)
    cancellation_token = Column(String(64), unique=True, nullable=True)
    cancellation_token_expires = Column(DateTime(timezone=True), nullable=True)

    # Notificaciones enviadas
    notification_email_sent = Column(Boolean, default=False)
    notification_push_sent = Column(Boolean, default=False)
    notification_sms_sent = Column(Boolean, default=False)

    # Marcado como principal
    is_primary = Column(Boolean, default=False)

    # Uso
    times_used = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    total_withdrawn = Column(String(50), default="0")  # Para evitar problemas de precisión

    # Quién lo agregó/aprobó
    added_from_ip = Column(INET, nullable=True)
    added_from_device_id = Column(UUID(as_uuid=True), ForeignKey("user_devices.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    user = relationship("User", backref="withdrawal_whitelist")
    added_from_device = relationship("UserDevice", foreign_keys=[added_from_device_id])

    __table_args__ = (
        Index("ix_whitelist_user_status", "user_id", "status"),
        Index("ix_whitelist_quarantine", "quarantine_ends_at"),
        UniqueConstraint("user_id", "address_hash", name="uq_whitelist_user_address"),
    )

    @staticmethod
    def generate_cancellation_token() -> str:
        """Genera token único para cancelación."""
        return secrets.token_urlsafe(32)

    @property
    def is_in_quarantine(self) -> bool:
        """Verifica si está en período de cuarentena."""
        if self.status != WhitelistStatus.PENDING:
            return False
        return datetime.utcnow() < self.quarantine_ends_at.replace(tzinfo=None)

    @property
    def can_be_used(self) -> bool:
        """Verifica si puede usarse para retiros."""
        return self.status == WhitelistStatus.ACTIVE


class UserDevice(Base):
    """
    Dispositivos registrados del usuario.

    Implementa tracking de dispositivos con:
    - Fingerprinting del dispositivo
    - Geolocalización aproximada
    - Score de riesgo
    - Notificación en primer uso
    """
    __tablename__ = "user_devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Usuario
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Fingerprint del dispositivo
    device_fingerprint = Column(String(64), nullable=False, index=True)

    # User Agent
    user_agent = Column(Text, nullable=True)
    browser_name = Column(String(50), nullable=True)
    browser_version = Column(String(20), nullable=True)
    os_name = Column(String(50), nullable=True)
    os_version = Column(String(20), nullable=True)
    device_type = Column(String(20), nullable=True)  # desktop, mobile, tablet

    # Geolocalización
    last_ip = Column(INET, nullable=True)
    last_country = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    last_city = Column(String(100), nullable=True)
    last_region = Column(String(100), nullable=True)

    # Detección de riesgo
    is_vpn = Column(Boolean, default=False)
    is_tor = Column(Boolean, default=False)
    is_proxy = Column(Boolean, default=False)
    risk_score = Column(Integer, default=0)  # 0-100

    # Estado
    status = Column(
        SQLEnum(DeviceStatus, name="device_status_enum", create_type=False),
        default=DeviceStatus.UNKNOWN,
        nullable=False
    )

    # Etiqueta del usuario
    device_name = Column(String(100), nullable=True)

    # Uso
    first_seen_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    login_count = Column(Integer, default=0)

    # Notificación
    notification_sent = Column(Boolean, default=False)
    trusted_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    # Relaciones
    user = relationship("User", backref="devices")

    __table_args__ = (
        Index("ix_device_user_fingerprint", "user_id", "device_fingerprint"),
        Index("ix_device_status", "status"),
        Index("ix_device_last_seen", "last_seen_at"),
    )


class UserSession(Base):
    """
    Sesiones activas del usuario.

    Permite:
    - Ver todas las sesiones activas
    - Cerrar sesiones remotas
    - Detectar sesiones sospechosas
    """
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Usuario
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Dispositivo asociado
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_devices.id", ondelete="SET NULL"),
        nullable=True
    )

    # Token de sesión (hash)
    session_token_hash = Column(String(64), unique=True, nullable=False)
    refresh_token_hash = Column(String(64), nullable=True)

    # IP y ubicación
    ip_address = Column(INET, nullable=True)
    country = Column(String(2), nullable=True)
    city = Column(String(100), nullable=True)

    # Estado
    is_active = Column(Boolean, default=True)
    is_current = Column(Boolean, default=False)  # Sesión actual del usuario

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_activity_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    user = relationship("User", backref="sessions")
    device = relationship("UserDevice", backref="sessions")

    __table_args__ = (
        Index("ix_session_user_active", "user_id", "is_active"),
        Index("ix_session_expires", "expires_at"),
    )


class PasswordHistory(Base):
    """
    Historial de contraseñas del usuario.

    Previene reutilización de las últimas N contraseñas.
    """
    __tablename__ = "password_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Usuario
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Hash de la contraseña (bcrypt/argon2)
    password_hash = Column(Text, nullable=False)

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    user = relationship("User", backref="password_history")

    __table_args__ = (
        Index("ix_password_history_user", "user_id", "created_at"),
    )


class AccountFreeze(Base):
    """
    Registro de congelamiento de cuenta.

    El usuario puede congelar su cuenta temporalmente.
    El descongelamiento requiere verificación por email.
    """
    __tablename__ = "account_freezes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Usuario
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Razón
    reason = Column(
        SQLEnum(AccountFreezeReason, name="account_freeze_reason_enum", create_type=False),
        nullable=False
    )
    reason_details = Column(Text, nullable=True)

    # Estado
    is_active = Column(Boolean, default=True)

    # Token para descongelar
    unfreeze_token = Column(String(64), unique=True, nullable=True)
    unfreeze_token_expires = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    frozen_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    unfrozen_at = Column(DateTime(timezone=True), nullable=True)

    # IP desde donde se congeló/descongeló
    frozen_from_ip = Column(INET, nullable=True)
    unfrozen_from_ip = Column(INET, nullable=True)

    # Quién descongeló (para casos de soporte)
    unfrozen_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    # Relaciones
    user = relationship("User", foreign_keys=[user_id], backref="account_freezes")
    unfrozen_by_user = relationship("User", foreign_keys=[unfrozen_by])

    __table_args__ = (
        Index("ix_freeze_user_active", "user_id", "is_active"),
    )

    @staticmethod
    def generate_unfreeze_token() -> str:
        """Genera token único para descongelar."""
        return secrets.token_urlsafe(32)


class AntiPhishingPhrase(Base):
    """
    Frase anti-phishing del usuario.

    Se muestra en todos los emails transaccionales
    para que el usuario verifique autenticidad.
    """
    __tablename__ = "anti_phishing_phrases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Usuario (1:1)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    # Frase secreta (cifrada)
    phrase_encrypted = Column(Text, nullable=False)

    # Hint para recordar (opcional)
    phrase_hint = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    # Relaciones
    user = relationship("User", backref="anti_phishing_phrase", uselist=False)


class MFABackupCode(Base):
    """
    Códigos de respaldo para MFA.

    8 códigos de un solo uso generados al activar MFA.
    """
    __tablename__ = "mfa_backup_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Usuario
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Código (hash)
    code_hash = Column(String(64), nullable=False)

    # Estado
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    used_from_ip = Column(INET, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    user = relationship("User", backref="mfa_backup_codes")

    __table_args__ = (
        Index("ix_backup_code_user", "user_id", "is_used"),
    )

    @staticmethod
    def generate_codes(count: int = 8) -> list[str]:
        """Genera códigos de respaldo legibles."""
        codes = []
        for _ in range(count):
            # Formato: XXXX-XXXX (8 caracteres alfanuméricos)
            code = secrets.token_hex(4).upper()
            formatted = f"{code[:4]}-{code[4:]}"
            codes.append(formatted)
        return codes
