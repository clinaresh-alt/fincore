"""
Modelos para Préstamos con Colateral.
Sistema de lending con garantía en cripto/tokens.
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
import secrets

from app.core.database import Base


class LoanStatus(str, enum.Enum):
    """Estado del préstamo."""
    DRAFT = "draft"  # Borrador
    PENDING_COLLATERAL = "pending_collateral"  # Esperando depósito de colateral
    PENDING_APPROVAL = "pending_approval"  # En revisión
    APPROVED = "approved"  # Aprobado, pendiente de desembolso
    ACTIVE = "active"  # Activo/Vigente
    MARGIN_CALL = "margin_call"  # Llamada de margen
    LIQUIDATING = "liquidating"  # En proceso de liquidación
    LIQUIDATED = "liquidated"  # Liquidado
    REPAID = "repaid"  # Pagado completamente
    DEFAULTED = "defaulted"  # En default
    CANCELLED = "cancelled"  # Cancelado


class CollateralType(str, enum.Enum):
    """Tipo de colateral."""
    CRYPTO = "crypto"  # Criptomonedas
    TOKEN = "token"  # Tokens de proyectos
    STABLECOIN = "stablecoin"  # Stablecoins
    NFT = "nft"  # NFTs (future)


class CollateralStatus(str, enum.Enum):
    """Estado del colateral."""
    PENDING = "pending"
    LOCKED = "locked"
    PARTIALLY_RELEASED = "partially_released"
    RELEASED = "released"
    LIQUIDATED = "liquidated"


class PaymentType(str, enum.Enum):
    """Tipo de pago de préstamo."""
    SCHEDULED = "scheduled"  # Pago programado
    EARLY = "early"  # Pago anticipado
    PARTIAL = "partial"  # Pago parcial
    FULL = "full"  # Pago total
    INTEREST_ONLY = "interest_only"  # Solo intereses
    LIQUIDATION = "liquidation"  # Por liquidación


class LoanProduct(Base):
    """
    Producto de préstamo.
    Define las condiciones del préstamo.
    """
    __tablename__ = "loan_products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)

    # Estado
    is_active = Column(Boolean, default=True)

    # Moneda del préstamo
    loan_currency = Column(String(10), nullable=False)  # MXN, USDC

    # Colaterales aceptados
    accepted_collaterals = Column(JSONB, default=[])  # ["BTC", "ETH", "USDC"]

    # Tasas de interés
    interest_rate_annual = Column(Numeric(8, 4), nullable=False)  # APR
    interest_rate_monthly = Column(Numeric(8, 4))
    interest_type = Column(String(20), default="simple")  # simple, compound

    # Loan-to-Value (LTV)
    max_ltv = Column(Numeric(5, 2), nullable=False)  # Ej: 70.00 = 70%
    initial_ltv = Column(Numeric(5, 2), nullable=False)  # LTV inicial requerido
    margin_call_ltv = Column(Numeric(5, 2), nullable=False)  # LTV para margin call
    liquidation_ltv = Column(Numeric(5, 2), nullable=False)  # LTV para liquidación

    # Límites
    min_loan_amount = Column(Numeric(18, 2), nullable=False)
    max_loan_amount = Column(Numeric(18, 2))
    min_term_days = Column(Integer, default=30)
    max_term_days = Column(Integer, default=365)

    # Comisiones
    origination_fee_percent = Column(Numeric(5, 2), default=0)
    early_repayment_fee_percent = Column(Numeric(5, 2), default=0)
    late_payment_fee_percent = Column(Numeric(5, 2), default=5)
    liquidation_fee_percent = Column(Numeric(5, 2), default=10)

    # Frecuencia de pago
    payment_frequency = Column(String(20), default="monthly")  # weekly, biweekly, monthly

    # Período de gracia
    grace_period_days = Column(Integer, default=3)

    # KYC requerido
    min_kyc_level = Column(Integer, default=2)

    # Metadata
    terms_url = Column(String(500))
    risk_disclosure = Column(Text)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    loans = relationship("Loan", back_populates="product")

    __table_args__ = (
        CheckConstraint("max_ltv > initial_ltv", name="check_ltv_order"),
        CheckConstraint("margin_call_ltv > initial_ltv", name="check_margin_ltv"),
        CheckConstraint("liquidation_ltv > margin_call_ltv", name="check_liquidation_ltv"),
        Index("idx_loan_product_active", "is_active"),
    )


class Loan(Base):
    """
    Préstamo con colateral.
    """
    __tablename__ = "loans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loan_number = Column(String(20), unique=True, nullable=False)

    # Usuario y producto
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False
    )
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_products.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Monto del préstamo
    principal = Column(Numeric(18, 8), nullable=False)
    currency = Column(String(10), nullable=False)

    # Tasas (snapshot al momento del préstamo)
    interest_rate = Column(Numeric(8, 4), nullable=False)
    origination_fee = Column(Numeric(18, 8), default=0)

    # Plazo
    term_days = Column(Integer, nullable=False)
    start_date = Column(DateTime(timezone=True))
    maturity_date = Column(DateTime(timezone=True))

    # Estado
    status = Column(
        SQLEnum(LoanStatus, name="loan_status_enum", create_type=False),
        default=LoanStatus.DRAFT
    )

    # Balances
    outstanding_principal = Column(Numeric(18, 8))  # Principal pendiente
    accrued_interest = Column(Numeric(18, 8), default=0)  # Intereses acumulados
    total_paid = Column(Numeric(18, 8), default=0)  # Total pagado
    total_interest_paid = Column(Numeric(18, 8), default=0)  # Intereses pagados

    # Próximo pago
    next_payment_date = Column(DateTime(timezone=True))
    next_payment_amount = Column(Numeric(18, 8))
    payments_made = Column(Integer, default=0)
    payments_total = Column(Integer)

    # LTV actual
    current_ltv = Column(Numeric(5, 2))
    last_ltv_update = Column(DateTime(timezone=True))

    # Colateral total (valor en USD)
    total_collateral_value_usd = Column(Numeric(18, 2), default=0)

    # Flags
    is_margin_call = Column(Boolean, default=False)
    margin_call_at = Column(DateTime(timezone=True))
    margin_call_deadline = Column(DateTime(timezone=True))

    # Auto-repago (desde balance del usuario)
    auto_repay_enabled = Column(Boolean, default=False)

    # Metadata
    metadata = Column(JSONB, default={})
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    approved_at = Column(DateTime(timezone=True))
    disbursed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime(timezone=True))

    # Relaciones
    user = relationship("User", backref="loans")
    product = relationship("LoanProduct", back_populates="loans")
    collaterals = relationship("LoanCollateral", back_populates="loan")
    payments = relationship("LoanPayment", back_populates="loan")
    liquidation_events = relationship("LiquidationEvent", back_populates="loan")

    __table_args__ = (
        CheckConstraint("principal > 0", name="check_loan_principal_positive"),
        Index("idx_loan_user", "user_id"),
        Index("idx_loan_status", "status"),
        Index("idx_loan_maturity", "maturity_date"),
    )

    @staticmethod
    def generate_loan_number() -> str:
        """Genera número de préstamo único."""
        timestamp = datetime.utcnow().strftime("%y%m%d")
        random_part = secrets.token_hex(4).upper()
        return f"LN{timestamp}{random_part}"

    @property
    def total_outstanding(self) -> float:
        """Monto total pendiente (principal + intereses)."""
        return float((self.outstanding_principal or 0) + (self.accrued_interest or 0))

    @property
    def health_factor(self) -> float:
        """Factor de salud del préstamo (> 1 es sano)."""
        if self.total_outstanding == 0:
            return float("inf")
        # health_factor = (collateral_value * liquidation_ltv) / outstanding
        # Simplificado: inverso del LTV actual vs liquidation LTV
        if self.current_ltv and self.product:
            liquidation_ltv = float(self.product.liquidation_ltv)
            return liquidation_ltv / float(self.current_ltv)
        return 1.0


class LoanCollateral(Base):
    """
    Colateral depositado para un préstamo.
    """
    __tablename__ = "loan_collaterals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Préstamo
    loan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loans.id", ondelete="RESTRICT"),
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Tipo de colateral
    collateral_type = Column(
        SQLEnum(CollateralType, name="collateral_type_enum", create_type=False),
        nullable=False
    )

    # Asset
    asset_symbol = Column(String(20), nullable=False)  # BTC, ETH, USDC
    asset_network = Column(String(20))  # ethereum, polygon, etc.
    asset_contract = Column(String(100))  # Para tokens

    # Cantidad
    amount = Column(Numeric(18, 8), nullable=False)
    amount_released = Column(Numeric(18, 8), default=0)
    amount_liquidated = Column(Numeric(18, 8), default=0)

    # Valor al momento del depósito
    price_at_deposit = Column(Numeric(18, 8), nullable=False)
    value_usd_at_deposit = Column(Numeric(18, 2), nullable=False)

    # Valor actual
    current_price = Column(Numeric(18, 8))
    current_value_usd = Column(Numeric(18, 2))
    last_price_update = Column(DateTime(timezone=True))

    # Estado
    status = Column(
        SQLEnum(CollateralStatus, name="collateral_status_enum", create_type=False),
        default=CollateralStatus.PENDING
    )

    # Dirección de custodia (si es crypto)
    custody_address = Column(String(100))
    deposit_tx_hash = Column(String(100))
    release_tx_hash = Column(String(100))

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    locked_at = Column(DateTime(timezone=True))
    released_at = Column(DateTime(timezone=True))

    # Relaciones
    loan = relationship("Loan", back_populates="collaterals")
    user = relationship("User", backref="loan_collaterals")

    __table_args__ = (
        CheckConstraint("amount > 0", name="check_collateral_amount_positive"),
        Index("idx_collateral_loan", "loan_id"),
        Index("idx_collateral_status", "status"),
    )

    @property
    def amount_locked(self) -> float:
        """Cantidad actualmente bloqueada."""
        return float(self.amount - (self.amount_released or 0) - (self.amount_liquidated or 0))


class LoanPayment(Base):
    """
    Pago de préstamo.
    """
    __tablename__ = "loan_payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_number = Column(String(20), unique=True, nullable=False)

    # Préstamo
    loan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loans.id", ondelete="RESTRICT"),
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Tipo de pago
    payment_type = Column(
        SQLEnum(PaymentType, name="payment_type_enum", create_type=False),
        nullable=False
    )

    # Montos
    total_amount = Column(Numeric(18, 8), nullable=False)
    principal_amount = Column(Numeric(18, 8), default=0)
    interest_amount = Column(Numeric(18, 8), default=0)
    fee_amount = Column(Numeric(18, 8), default=0)
    currency = Column(String(10), nullable=False)

    # Balance después del pago
    principal_after = Column(Numeric(18, 8))
    interest_after = Column(Numeric(18, 8))

    # Número de cuota (para pagos programados)
    installment_number = Column(Integer)
    scheduled_date = Column(DateTime(timezone=True))
    is_late = Column(Boolean, default=False)
    days_late = Column(Integer, default=0)

    # Método de pago
    payment_method = Column(String(30))  # balance, bank_transfer, crypto
    payment_reference = Column(String(100))

    # Estado
    status = Column(String(20), default="completed")  # pending, completed, failed, reversed

    # Metadata
    metadata = Column(JSONB, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    processed_at = Column(DateTime(timezone=True))

    # Relaciones
    loan = relationship("Loan", back_populates="payments")
    user = relationship("User", backref="loan_payments")

    __table_args__ = (
        CheckConstraint("total_amount > 0", name="check_payment_amount_positive"),
        Index("idx_payment_loan", "loan_id"),
        Index("idx_payment_created", "created_at"),
    )

    @staticmethod
    def generate_payment_number() -> str:
        """Genera número de pago único."""
        timestamp = datetime.utcnow().strftime("%y%m%d%H%M%S")
        random_part = secrets.token_hex(2).upper()
        return f"LP{timestamp}{random_part}"


class LiquidationEvent(Base):
    """
    Evento de liquidación de colateral.
    """
    __tablename__ = "liquidation_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    liquidation_id = Column(String(20), unique=True, nullable=False)

    # Préstamo
    loan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loans.id", ondelete="RESTRICT"),
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Trigger
    trigger_reason = Column(String(50), nullable=False)  # ltv_breach, default, manual
    trigger_ltv = Column(Numeric(5, 2))
    trigger_health_factor = Column(Numeric(8, 4))

    # Deuda al momento de liquidación
    outstanding_debt = Column(Numeric(18, 8), nullable=False)
    debt_currency = Column(String(10), nullable=False)

    # Colateral liquidado
    collateral_asset = Column(String(20), nullable=False)
    collateral_amount = Column(Numeric(18, 8), nullable=False)
    collateral_price = Column(Numeric(18, 8), nullable=False)
    collateral_value_usd = Column(Numeric(18, 2), nullable=False)

    # Resultados
    debt_repaid = Column(Numeric(18, 8))
    liquidation_fee = Column(Numeric(18, 8))
    surplus_returned = Column(Numeric(18, 8))  # Si colateral > deuda

    # Ejecución
    status = Column(String(20), default="pending")  # pending, executing, completed, failed
    execution_price = Column(Numeric(18, 8))  # Precio de venta real
    execution_tx_hash = Column(String(100))

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    executed_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # Relaciones
    loan = relationship("Loan", back_populates="liquidation_events")
    user = relationship("User", backref="liquidation_events")

    __table_args__ = (
        Index("idx_liquidation_loan", "loan_id"),
        Index("idx_liquidation_status", "status"),
    )

    @staticmethod
    def generate_liquidation_id() -> str:
        """Genera ID de liquidación único."""
        timestamp = datetime.utcnow().strftime("%y%m%d%H%M%S")
        random_part = secrets.token_hex(2).upper()
        return f"LIQ{timestamp}{random_part}"


class LoanOffer(Base):
    """
    Oferta de préstamo pre-aprobada para un usuario.
    """
    __tablename__ = "loan_offers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offer_code = Column(String(20), unique=True, nullable=False)

    # Usuario
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_products.id", ondelete="CASCADE"),
        nullable=False
    )

    # Oferta
    max_amount = Column(Numeric(18, 2), nullable=False)
    interest_rate = Column(Numeric(8, 4), nullable=False)  # Tasa personalizada
    max_term_days = Column(Integer)

    # Condiciones especiales
    special_conditions = Column(JSONB, default={})
    message = Column(Text)

    # Vigencia
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)

    # Uso
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime(timezone=True))
    resulting_loan_id = Column(UUID(as_uuid=True), ForeignKey("loans.id"))

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    user = relationship("User", backref="loan_offers")
    product = relationship("LoanProduct")
    resulting_loan = relationship("Loan")

    __table_args__ = (
        Index("idx_offer_user", "user_id"),
        Index("idx_offer_active", "is_active", "valid_until"),
    )

    @staticmethod
    def generate_offer_code() -> str:
        """Genera código de oferta único."""
        return secrets.token_urlsafe(12).upper()[:16]
