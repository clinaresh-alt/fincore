"""
Modelos para Fincore Earn - Productos de Rendimiento.
Sistema de ahorro e inversión con rendimientos.
"""
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey,
    Text, Numeric, Enum as SQLEnum, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid
import enum

from app.core.database import Base


class EarnProductType(str, enum.Enum):
    """Tipo de producto de rendimiento."""
    FLEXIBLE = "flexible"  # Retiro cuando quieras
    FIXED_30 = "fixed_30"  # 30 días plazo fijo
    FIXED_60 = "fixed_60"  # 60 días
    FIXED_90 = "fixed_90"  # 90 días
    FIXED_180 = "fixed_180"  # 180 días
    FIXED_365 = "fixed_365"  # 1 año
    STAKING = "staking"  # Staking de tokens


class EarnProductStatus(str, enum.Enum):
    """Estado del producto."""
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    COMING_SOON = "coming_soon"


class EarnPositionStatus(str, enum.Enum):
    """Estado de la posición del usuario."""
    ACTIVE = "active"
    PENDING_WITHDRAWAL = "pending_withdrawal"
    WITHDRAWN = "withdrawn"
    LIQUIDATED = "liquidated"


class YieldDistributionStatus(str, enum.Enum):
    """Estado de distribución de rendimientos."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class EarnProduct(Base):
    """
    Producto de rendimiento/ahorro.
    Define las condiciones del producto.
    """
    __tablename__ = "earn_products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)

    # Tipo y estado
    product_type = Column(
        SQLEnum(EarnProductType, name="earn_product_type_enum", create_type=False),
        nullable=False
    )
    status = Column(
        SQLEnum(EarnProductStatus, name="earn_product_status_enum", create_type=False),
        default=EarnProductStatus.ACTIVE
    )

    # Moneda/Asset
    currency = Column(String(10), nullable=False)  # MXN, USDC, etc.
    is_crypto = Column(Boolean, default=False)

    # Rendimiento
    apy_base = Column(Numeric(8, 4), nullable=False)  # APY base en %
    apy_bonus = Column(Numeric(8, 4), default=0)  # Bonus promocional
    apy_max = Column(Numeric(8, 4))  # APY máximo posible

    # Rendimiento variable (para productos con APY dinámico)
    is_variable_rate = Column(Boolean, default=False)
    rate_update_frequency = Column(String(20))  # daily, weekly, etc.

    # Límites
    min_deposit = Column(Numeric(18, 8), nullable=False)
    max_deposit = Column(Numeric(18, 8), nullable=True)  # null = sin límite
    total_capacity = Column(Numeric(18, 8), nullable=True)  # Capacidad total del producto
    current_tvl = Column(Numeric(18, 8), default=0)  # Total Value Locked

    # Plazo (para productos de plazo fijo)
    lock_period_days = Column(Integer, default=0)  # 0 = flexible
    early_withdrawal_penalty = Column(Numeric(8, 4), default=0)  # % penalización

    # Frecuencia de pago de rendimientos
    yield_frequency = Column(String(20), default="daily")  # daily, weekly, monthly
    compound_enabled = Column(Boolean, default=True)  # Auto-compound

    # Riesgo
    risk_level = Column(Integer, default=1)  # 1-5
    risk_description = Column(Text)

    # UI
    icon_url = Column(String(500))
    color = Column(String(20))
    display_order = Column(Integer, default=0)

    # Términos
    terms_url = Column(String(500))
    terms_version = Column(String(20))

    # Promoción
    is_promoted = Column(Boolean, default=False)
    promotion_end_at = Column(DateTime(timezone=True))
    promotion_message = Column(String(255))

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    positions = relationship("EarnPosition", back_populates="product")

    __table_args__ = (
        CheckConstraint("apy_base >= 0", name="check_apy_positive"),
        CheckConstraint("min_deposit > 0", name="check_min_deposit_positive"),
        Index("idx_earn_product_status", "status"),
        Index("idx_earn_product_type", "product_type"),
        Index("idx_earn_product_currency", "currency"),
    )

    @property
    def current_apy(self) -> float:
        """APY actual incluyendo bonus."""
        return float(self.apy_base + (self.apy_bonus or 0))

    @property
    def available_capacity(self) -> float:
        """Capacidad disponible para depósitos."""
        if self.total_capacity is None:
            return float("inf")
        return float(self.total_capacity - self.current_tvl)


class EarnPosition(Base):
    """
    Posición del usuario en un producto de rendimiento.
    """
    __tablename__ = "earn_positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    position_number = Column(String(20), unique=True, nullable=False)

    # Usuario y producto
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False
    )
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("earn_products.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Monto
    principal = Column(Numeric(18, 8), nullable=False)  # Capital inicial
    accrued_yield = Column(Numeric(18, 8), default=0)  # Rendimiento acumulado
    total_withdrawn = Column(Numeric(18, 8), default=0)  # Total retirado
    currency = Column(String(10), nullable=False)

    # APY bloqueado (para productos de tasa fija)
    locked_apy = Column(Numeric(8, 4))

    # Estado
    status = Column(
        SQLEnum(EarnPositionStatus, name="earn_position_status_enum", create_type=False),
        default=EarnPositionStatus.ACTIVE
    )

    # Fechas de plazo
    start_date = Column(DateTime(timezone=True), default=datetime.utcnow)
    maturity_date = Column(DateTime(timezone=True), nullable=True)  # null = flexible
    last_yield_date = Column(DateTime(timezone=True))  # Último cálculo de rendimiento

    # Auto-compound
    auto_compound = Column(Boolean, default=True)
    compound_earnings = Column(Numeric(18, 8), default=0)  # Rendimiento reinvertido

    # Auto-renewal (para productos de plazo fijo)
    auto_renew = Column(Boolean, default=False)
    renewal_count = Column(Integer, default=0)

    # Metadata
    metadata = Column(JSONB, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    withdrawn_at = Column(DateTime(timezone=True))

    # Relaciones
    user = relationship("User", backref="earn_positions")
    product = relationship("EarnProduct", back_populates="positions")
    transactions = relationship("EarnTransaction", back_populates="position")
    yield_distributions = relationship("YieldDistribution", back_populates="position")

    __table_args__ = (
        CheckConstraint("principal > 0", name="check_principal_positive"),
        Index("idx_position_user", "user_id"),
        Index("idx_position_product", "product_id"),
        Index("idx_position_status", "status"),
    )

    @staticmethod
    def generate_position_number() -> str:
        """Genera número de posición único."""
        import secrets
        timestamp = datetime.utcnow().strftime("%y%m%d")
        random_part = secrets.token_hex(4).upper()
        return f"EP{timestamp}{random_part}"

    @property
    def current_value(self) -> float:
        """Valor actual de la posición."""
        return float(self.principal + self.accrued_yield + self.compound_earnings - self.total_withdrawn)

    @property
    def total_yield(self) -> float:
        """Rendimiento total generado."""
        return float(self.accrued_yield + self.compound_earnings)

    @property
    def is_mature(self) -> bool:
        """Indica si la posición ha madurado (plazo cumplido)."""
        if self.maturity_date is None:
            return True  # Flexible siempre disponible
        return datetime.utcnow() >= self.maturity_date


class EarnTransactionType(str, enum.Enum):
    """Tipo de transacción en Earn."""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    YIELD_PAYMENT = "yield_payment"
    COMPOUND = "compound"
    EARLY_WITHDRAWAL = "early_withdrawal"
    PENALTY = "penalty"
    BONUS = "bonus"


class EarnTransaction(Base):
    """
    Transacción en producto de rendimiento.
    """
    __tablename__ = "earn_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_number = Column(String(25), unique=True, nullable=False)

    # Posición
    position_id = Column(
        UUID(as_uuid=True),
        ForeignKey("earn_positions.id", ondelete="RESTRICT"),
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Tipo y monto
    transaction_type = Column(
        SQLEnum(EarnTransactionType, name="earn_tx_type_enum", create_type=False),
        nullable=False
    )
    amount = Column(Numeric(18, 8), nullable=False)
    currency = Column(String(10), nullable=False)

    # Para rendimientos: APY aplicado
    applied_apy = Column(Numeric(8, 4))
    calculation_days = Column(Integer)

    # Balance después de la transacción
    balance_after = Column(Numeric(18, 8))

    # Descripción
    description = Column(String(255))

    # Metadata
    metadata = Column(JSONB, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    position = relationship("EarnPosition", back_populates="transactions")
    user = relationship("User", backref="earn_transactions")

    __table_args__ = (
        Index("idx_earn_tx_position", "position_id"),
        Index("idx_earn_tx_user", "user_id"),
        Index("idx_earn_tx_type", "transaction_type"),
        Index("idx_earn_tx_created", "created_at"),
    )

    @staticmethod
    def generate_transaction_number() -> str:
        """Genera número de transacción único."""
        import secrets
        timestamp = datetime.utcnow().strftime("%y%m%d%H%M%S")
        random_part = secrets.token_hex(3).upper()
        return f"ET{timestamp}{random_part}"


class YieldDistribution(Base):
    """
    Distribución de rendimientos.
    Registro de cada pago de yield.
    """
    __tablename__ = "yield_distributions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    distribution_id = Column(String(30), unique=True, nullable=False)

    # Posición y producto
    position_id = Column(
        UUID(as_uuid=True),
        ForeignKey("earn_positions.id", ondelete="RESTRICT"),
        nullable=False
    )
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("earn_products.id", ondelete="RESTRICT"),
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Período de cálculo
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)

    # Cálculo
    principal_amount = Column(Numeric(18, 8), nullable=False)
    applied_apy = Column(Numeric(8, 4), nullable=False)
    days_calculated = Column(Integer, nullable=False)

    # Yield
    gross_yield = Column(Numeric(18, 8), nullable=False)
    fee = Column(Numeric(18, 8), default=0)
    net_yield = Column(Numeric(18, 8), nullable=False)
    currency = Column(String(10), nullable=False)

    # Destino
    is_compounded = Column(Boolean, default=False)
    is_withdrawn = Column(Boolean, default=False)

    # Estado
    status = Column(
        SQLEnum(YieldDistributionStatus, name="yield_dist_status_enum", create_type=False),
        default=YieldDistributionStatus.PENDING
    )

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    processed_at = Column(DateTime(timezone=True))

    # Relaciones
    position = relationship("EarnPosition", back_populates="yield_distributions")
    product = relationship("EarnProduct")
    user = relationship("User", backref="yield_distributions")

    __table_args__ = (
        Index("idx_yield_position", "position_id"),
        Index("idx_yield_user", "user_id"),
        Index("idx_yield_period", "period_start", "period_end"),
        Index("idx_yield_status", "status"),
    )

    @staticmethod
    def generate_distribution_id() -> str:
        """Genera ID de distribución único."""
        import secrets
        timestamp = datetime.utcnow().strftime("%y%m%d")
        random_part = secrets.token_hex(6).upper()
        return f"YD{timestamp}{random_part}"


class EarnPromotion(Base):
    """
    Promociones y bonos de Earn.
    """
    __tablename__ = "earn_promotions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)

    # Tipo de promoción
    promotion_type = Column(String(30), nullable=False)  # apy_boost, bonus_deposit, cashback

    # Valor del beneficio
    bonus_value = Column(Numeric(18, 8), nullable=False)
    bonus_type = Column(String(20), nullable=False)  # percentage, fixed

    # Aplicabilidad
    applicable_products = Column(JSONB, default=[])  # Lista de product_ids, vacío = todos
    min_deposit = Column(Numeric(18, 8))
    min_lock_days = Column(Integer)

    # Límites
    max_uses_total = Column(Integer)
    max_uses_per_user = Column(Integer, default=1)
    current_uses = Column(Integer, default=0)
    total_budget = Column(Numeric(18, 8))
    used_budget = Column(Numeric(18, 8), default=0)

    # Vigencia
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)

    # Requisitos
    new_users_only = Column(Boolean, default=False)
    kyc_required = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("idx_promo_code", "code"),
        Index("idx_promo_active", "is_active"),
        Index("idx_promo_dates", "start_date", "end_date"),
    )
