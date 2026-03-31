"""
Modelos para Tarjeta Débito FinCore.
Integración con emisor de tarjetas (BIN sponsor).
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


class CardStatus(str, enum.Enum):
    """Estado de la tarjeta."""
    PENDING = "pending"  # Solicitud en proceso
    ACTIVE = "active"  # Activa y funcional
    FROZEN = "frozen"  # Congelada temporalmente
    BLOCKED = "blocked"  # Bloqueada por seguridad
    EXPIRED = "expired"  # Expirada
    CANCELLED = "cancelled"  # Cancelada
    LOST = "lost"  # Reportada como perdida
    STOLEN = "stolen"  # Reportada como robada


class CardType(str, enum.Enum):
    """Tipo de tarjeta."""
    VIRTUAL = "virtual"  # Solo para compras online
    PHYSICAL = "physical"  # Tarjeta física


class CardNetwork(str, enum.Enum):
    """Red de la tarjeta."""
    VISA = "visa"
    MASTERCARD = "mastercard"


class CardTransactionStatus(str, enum.Enum):
    """Estado de transacción."""
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    DECLINED = "declined"
    REVERSED = "reversed"
    REFUNDED = "refunded"
    CHARGEBACK = "chargeback"


class CardTransactionType(str, enum.Enum):
    """Tipo de transacción."""
    PURCHASE = "purchase"
    ATM_WITHDRAWAL = "atm_withdrawal"
    REFUND = "refund"
    REVERSAL = "reversal"
    FEE = "fee"
    CASHBACK = "cashback"
    TRANSFER = "transfer"


class DebitCard(Base):
    """
    Tarjeta de débito vinculada a cuenta FinCore.
    """
    __tablename__ = "debit_cards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Usuario
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )

    # Identificadores de tarjeta
    card_id = Column(String(50), unique=True, nullable=False)  # ID del emisor
    card_token = Column(String(100), unique=True, nullable=False)  # Token para operaciones
    last_four = Column(String(4), nullable=False)  # Últimos 4 dígitos
    bin_number = Column(String(8))  # BIN (primeros 6-8 dígitos)

    # Tipo y red
    card_type = Column(
        SQLEnum(CardType, name="card_type_enum", create_type=False),
        nullable=False
    )
    card_network = Column(
        SQLEnum(CardNetwork, name="card_network_enum", create_type=False),
        default=CardNetwork.VISA
    )

    # Estado
    status = Column(
        SQLEnum(CardStatus, name="card_status_enum", create_type=False),
        default=CardStatus.PENDING
    )

    # Información de la tarjeta (encriptada/tokenizada)
    cardholder_name = Column(String(100), nullable=False)
    expiry_month = Column(Integer, nullable=False)
    expiry_year = Column(Integer, nullable=False)

    # Para tarjetas físicas
    shipping_address_id = Column(UUID(as_uuid=True), nullable=True)
    shipping_status = Column(String(30))  # ordered, shipped, delivered
    tracking_number = Column(String(100))
    delivered_at = Column(DateTime(timezone=True))

    # PIN (hash)
    pin_set = Column(Boolean, default=False)
    pin_attempts = Column(Integer, default=0)
    pin_locked_until = Column(DateTime(timezone=True))

    # Configuración
    is_contactless_enabled = Column(Boolean, default=True)
    is_online_enabled = Column(Boolean, default=True)
    is_atm_enabled = Column(Boolean, default=True)
    is_international_enabled = Column(Boolean, default=False)

    # Límites personalizados
    daily_spend_limit = Column(Numeric(18, 2))
    monthly_spend_limit = Column(Numeric(18, 2))
    single_transaction_limit = Column(Numeric(18, 2))
    daily_atm_limit = Column(Numeric(18, 2))

    # Uso
    daily_spent = Column(Numeric(18, 2), default=0)
    monthly_spent = Column(Numeric(18, 2), default=0)
    last_spent_reset = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Notificaciones
    notify_all_transactions = Column(Boolean, default=True)
    notify_above_amount = Column(Numeric(18, 2))

    # Metadata del emisor
    issuer_data = Column(JSONB, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    activated_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    frozen_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))

    # Relaciones
    user = relationship("User", backref="debit_cards")
    transactions = relationship("CardTransaction", back_populates="card")
    limits = relationship("CardLimit", back_populates="card")

    __table_args__ = (
        Index("idx_card_user", "user_id"),
        Index("idx_card_status", "status"),
        Index("idx_card_card_id", "card_id"),
    )

    @staticmethod
    def generate_card_token() -> str:
        """Genera token único para la tarjeta."""
        return secrets.token_urlsafe(48)

    @property
    def is_usable(self) -> bool:
        """Indica si la tarjeta puede usarse."""
        return self.status == CardStatus.ACTIVE

    @property
    def expiry_display(self) -> str:
        """Muestra la fecha de expiración formateada."""
        return f"{self.expiry_month:02d}/{str(self.expiry_year)[-2:]}"

    @property
    def masked_number(self) -> str:
        """Número de tarjeta enmascarado."""
        return f"**** **** **** {self.last_four}"


class CardTransaction(Base):
    """
    Transacción de tarjeta de débito.
    """
    __tablename__ = "card_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(String(50), unique=True, nullable=False)

    # Tarjeta
    card_id = Column(
        UUID(as_uuid=True),
        ForeignKey("debit_cards.id", ondelete="RESTRICT"),
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Tipo y estado
    transaction_type = Column(
        SQLEnum(CardTransactionType, name="card_tx_type_enum", create_type=False),
        nullable=False
    )
    status = Column(
        SQLEnum(CardTransactionStatus, name="card_tx_status_enum", create_type=False),
        default=CardTransactionStatus.PENDING
    )

    # Montos
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), default="MXN")
    original_amount = Column(Numeric(18, 2))  # Si es diferente moneda
    original_currency = Column(String(3))
    exchange_rate = Column(Numeric(18, 8))
    fee = Column(Numeric(18, 2), default=0)

    # Comercio
    merchant_name = Column(String(255))
    merchant_category_code = Column(String(10))  # MCC
    merchant_category = Column(String(100))
    merchant_city = Column(String(100))
    merchant_country = Column(String(3))
    merchant_id = Column(String(50))

    # Detalles de la transacción
    authorization_code = Column(String(20))
    retrieval_reference = Column(String(30))
    is_contactless = Column(Boolean, default=False)
    is_online = Column(Boolean, default=False)
    is_international = Column(Boolean, default=False)
    is_recurring = Column(Boolean, default=False)

    # 3DS (para transacciones online)
    threed_secure = Column(Boolean, default=False)
    threed_secure_version = Column(String(10))

    # Código de respuesta
    response_code = Column(String(10))
    decline_reason = Column(String(100))

    # Para ATM
    atm_id = Column(String(50))
    atm_location = Column(String(255))

    # Transacción original (para refunds/reversals)
    original_transaction_id = Column(UUID(as_uuid=True), ForeignKey("card_transactions.id"))

    # Metadata
    metadata = Column(JSONB, default={})
    device_info = Column(JSONB, default={})

    # Balance después de transacción
    balance_after = Column(Numeric(18, 2))

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    authorized_at = Column(DateTime(timezone=True))
    captured_at = Column(DateTime(timezone=True))
    settled_at = Column(DateTime(timezone=True))

    # Relaciones
    card = relationship("DebitCard", back_populates="transactions")
    user = relationship("User", backref="card_transactions")
    original_transaction = relationship("CardTransaction", remote_side=[id])

    __table_args__ = (
        Index("idx_card_tx_card", "card_id"),
        Index("idx_card_tx_user", "user_id"),
        Index("idx_card_tx_status", "status"),
        Index("idx_card_tx_created", "created_at"),
        Index("idx_card_tx_merchant", "merchant_name"),
    )

    @staticmethod
    def generate_transaction_id() -> str:
        """Genera ID de transacción único."""
        timestamp = datetime.utcnow().strftime("%y%m%d%H%M%S")
        random_part = secrets.token_hex(4).upper()
        return f"CTX{timestamp}{random_part}"


class CardLimit(Base):
    """
    Límites personalizados por categoría/comercio.
    """
    __tablename__ = "card_limits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Tarjeta
    card_id = Column(
        UUID(as_uuid=True),
        ForeignKey("debit_cards.id", ondelete="CASCADE"),
        nullable=False
    )

    # Tipo de límite
    limit_type = Column(String(30), nullable=False)  # category, merchant, country

    # Identificador del límite
    limit_identifier = Column(String(50))  # MCC, merchant_id, country_code

    # Acción
    action = Column(String(20), default="limit")  # limit, block, allow

    # Límite (si aplica)
    daily_limit = Column(Numeric(18, 2))
    monthly_limit = Column(Numeric(18, 2))
    single_limit = Column(Numeric(18, 2))

    # Uso actual
    daily_used = Column(Numeric(18, 2), default=0)
    monthly_used = Column(Numeric(18, 2), default=0)

    # Estado
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    card = relationship("DebitCard", back_populates="limits")

    __table_args__ = (
        Index("idx_limit_card", "card_id"),
        Index("idx_limit_type", "limit_type", "limit_identifier"),
    )


class CardDispute(Base):
    """
    Disputas/Contracargos de transacciones.
    """
    __tablename__ = "card_disputes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dispute_number = Column(String(20), unique=True, nullable=False)

    # Transacción disputada
    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("card_transactions.id", ondelete="RESTRICT"),
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Razón
    reason_code = Column(String(10), nullable=False)
    reason_description = Column(String(255), nullable=False)
    user_description = Column(Text)

    # Monto disputado
    disputed_amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), default="MXN")

    # Estado
    status = Column(String(30), default="open")  # open, under_review, resolved_favor, resolved_against, closed
    resolution = Column(Text)
    resolution_date = Column(DateTime(timezone=True))

    # Crédito provisional
    provisional_credit_given = Column(Boolean, default=False)
    provisional_credit_amount = Column(Numeric(18, 2))
    provisional_credit_date = Column(DateTime(timezone=True))

    # Documentos
    documents = Column(JSONB, default=[])

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    transaction = relationship("CardTransaction", backref="disputes")
    user = relationship("User", backref="card_disputes")

    __table_args__ = (
        Index("idx_dispute_user", "user_id"),
        Index("idx_dispute_status", "status"),
    )

    @staticmethod
    def generate_dispute_number() -> str:
        """Genera número de disputa único."""
        timestamp = datetime.utcnow().strftime("%y%m%d")
        random_part = secrets.token_hex(3).upper()
        return f"DIS{timestamp}{random_part}"


class CardReward(Base):
    """
    Recompensas/Cashback de tarjeta.
    """
    __tablename__ = "card_rewards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Usuario y transacción
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )
    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("card_transactions.id", ondelete="SET NULL"),
        nullable=True
    )

    # Recompensa
    reward_type = Column(String(30), nullable=False)  # cashback, points, bonus
    amount = Column(Numeric(18, 8), nullable=False)
    currency = Column(String(10), default="MXN")

    # Descripción
    description = Column(String(255))
    category = Column(String(50))  # dining, travel, online, etc.

    # Estado
    status = Column(String(20), default="pending")  # pending, credited, expired
    credited_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    user = relationship("User", backref="card_rewards")
    transaction = relationship("CardTransaction", backref="rewards")

    __table_args__ = (
        Index("idx_reward_user", "user_id"),
        Index("idx_reward_status", "status"),
    )
