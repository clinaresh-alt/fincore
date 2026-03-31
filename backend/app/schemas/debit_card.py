"""
Schemas para Tarjeta de Débito FinCore.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from enum import Enum


class CardStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    FROZEN = "frozen"
    BLOCKED = "blocked"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    LOST = "lost"
    STOLEN = "stolen"


class CardType(str, Enum):
    VIRTUAL = "virtual"
    PHYSICAL = "physical"


class CardNetwork(str, Enum):
    VISA = "visa"
    MASTERCARD = "mastercard"


class CardTransactionStatus(str, Enum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    DECLINED = "declined"
    REVERSED = "reversed"
    REFUNDED = "refunded"
    CHARGEBACK = "chargeback"


class CardTransactionType(str, Enum):
    PURCHASE = "purchase"
    ATM_WITHDRAWAL = "atm_withdrawal"
    REFUND = "refund"
    REVERSAL = "reversal"
    FEE = "fee"
    CASHBACK = "cashback"
    TRANSFER = "transfer"


# =====================
# Card Schemas
# =====================

class DebitCardCreate(BaseModel):
    """Solicitar tarjeta de débito."""
    card_type: CardType
    card_network: CardNetwork = CardNetwork.VISA
    cardholder_name: str = Field(..., min_length=2, max_length=100)

    # Para tarjetas físicas
    shipping_address_id: Optional[UUID] = None

    # Configuración inicial
    daily_spend_limit: Optional[Decimal] = Field(None, gt=0)
    monthly_spend_limit: Optional[Decimal] = Field(None, gt=0)
    single_transaction_limit: Optional[Decimal] = Field(None, gt=0)
    daily_atm_limit: Optional[Decimal] = Field(None, gt=0)

    is_contactless_enabled: bool = True
    is_online_enabled: bool = True
    is_atm_enabled: bool = True
    is_international_enabled: bool = False

    @validator("shipping_address_id")
    def validate_shipping(cls, v, values):
        if values.get("card_type") == CardType.PHYSICAL and v is None:
            raise ValueError("Se requiere dirección de envío para tarjeta física")
        return v


class DebitCardResponse(BaseModel):
    """Respuesta de tarjeta de débito."""
    id: UUID
    user_id: UUID
    card_id: str
    last_four: str
    bin_number: Optional[str]
    card_type: CardType
    card_network: CardNetwork
    status: CardStatus
    cardholder_name: str
    expiry_month: int
    expiry_year: int
    expiry_display: str
    masked_number: str

    # Para tarjetas físicas
    shipping_status: Optional[str]
    tracking_number: Optional[str]
    delivered_at: Optional[datetime]

    # PIN
    pin_set: bool
    pin_locked_until: Optional[datetime]

    # Configuración
    is_contactless_enabled: bool
    is_online_enabled: bool
    is_atm_enabled: bool
    is_international_enabled: bool

    # Límites
    daily_spend_limit: Optional[Decimal]
    monthly_spend_limit: Optional[Decimal]
    single_transaction_limit: Optional[Decimal]
    daily_atm_limit: Optional[Decimal]

    # Uso
    daily_spent: Decimal
    monthly_spent: Decimal

    # Notificaciones
    notify_all_transactions: bool
    notify_above_amount: Optional[Decimal]

    # Timestamps
    created_at: datetime
    activated_at: Optional[datetime]
    frozen_at: Optional[datetime]

    class Config:
        from_attributes = True


class DebitCardList(BaseModel):
    """Lista de tarjetas de débito."""
    cards: List[DebitCardResponse]
    total: int
    active_count: int
    virtual_count: int
    physical_count: int


class DebitCardUpdate(BaseModel):
    """Actualizar configuración de tarjeta."""
    is_contactless_enabled: Optional[bool] = None
    is_online_enabled: Optional[bool] = None
    is_atm_enabled: Optional[bool] = None
    is_international_enabled: Optional[bool] = None
    daily_spend_limit: Optional[Decimal] = Field(None, gt=0)
    monthly_spend_limit: Optional[Decimal] = Field(None, gt=0)
    single_transaction_limit: Optional[Decimal] = Field(None, gt=0)
    daily_atm_limit: Optional[Decimal] = Field(None, gt=0)
    notify_all_transactions: Optional[bool] = None
    notify_above_amount: Optional[Decimal] = Field(None, gt=0)


class DebitCardActivate(BaseModel):
    """Activar tarjeta física."""
    last_four: str = Field(..., min_length=4, max_length=4, regex=r"^\d{4}$")
    cvv: str = Field(..., min_length=3, max_length=4, regex=r"^\d{3,4}$")


class DebitCardSetPIN(BaseModel):
    """Establecer PIN de tarjeta."""
    pin: str = Field(..., min_length=4, max_length=6, regex=r"^\d{4,6}$")
    confirm_pin: str = Field(..., min_length=4, max_length=6, regex=r"^\d{4,6}$")

    @validator("confirm_pin")
    def pins_match(cls, v, values):
        if "pin" in values and v != values["pin"]:
            raise ValueError("Los PINs no coinciden")
        return v


class DebitCardChangePIN(BaseModel):
    """Cambiar PIN de tarjeta."""
    current_pin: str = Field(..., min_length=4, max_length=6, regex=r"^\d{4,6}$")
    new_pin: str = Field(..., min_length=4, max_length=6, regex=r"^\d{4,6}$")
    confirm_pin: str = Field(..., min_length=4, max_length=6, regex=r"^\d{4,6}$")

    @validator("confirm_pin")
    def pins_match(cls, v, values):
        if "new_pin" in values and v != values["new_pin"]:
            raise ValueError("Los PINs no coinciden")
        return v


class DebitCardFreeze(BaseModel):
    """Congelar tarjeta."""
    reason: Optional[str] = Field(None, max_length=255)


class DebitCardReport(BaseModel):
    """Reportar tarjeta perdida/robada."""
    report_type: str = Field(..., regex=r"^(lost|stolen)$")
    description: Optional[str] = None
    request_replacement: bool = True
    shipping_address_id: Optional[UUID] = None


# =====================
# Card Transaction Schemas
# =====================

class CardTransactionResponse(BaseModel):
    """Respuesta de transacción de tarjeta."""
    id: UUID
    transaction_id: str
    card_id: UUID
    user_id: UUID
    transaction_type: CardTransactionType
    status: CardTransactionStatus

    # Montos
    amount: Decimal
    currency: str
    original_amount: Optional[Decimal]
    original_currency: Optional[str]
    exchange_rate: Optional[Decimal]
    fee: Decimal

    # Comercio
    merchant_name: Optional[str]
    merchant_category_code: Optional[str]
    merchant_category: Optional[str]
    merchant_city: Optional[str]
    merchant_country: Optional[str]

    # Detalles
    authorization_code: Optional[str]
    is_contactless: bool
    is_online: bool
    is_international: bool
    is_recurring: bool
    threed_secure: bool

    # Para declinadas
    decline_reason: Optional[str]

    # Balance
    balance_after: Optional[Decimal]

    # Timestamps
    created_at: datetime
    authorized_at: Optional[datetime]
    captured_at: Optional[datetime]
    settled_at: Optional[datetime]

    class Config:
        from_attributes = True


class CardTransactionList(BaseModel):
    """Lista de transacciones de tarjeta."""
    transactions: List[CardTransactionResponse]
    total: int
    page: int
    page_size: int
    total_spent: Decimal
    total_refunded: Decimal


# =====================
# Card Limit Schemas
# =====================

class CardLimitCreate(BaseModel):
    """Crear límite personalizado."""
    limit_type: str = Field(..., regex=r"^(category|merchant|country)$")
    limit_identifier: str = Field(..., max_length=50)
    action: str = Field(default="limit", regex=r"^(limit|block|allow)$")
    daily_limit: Optional[Decimal] = Field(None, ge=0)
    monthly_limit: Optional[Decimal] = Field(None, ge=0)
    single_limit: Optional[Decimal] = Field(None, ge=0)


class CardLimitResponse(BaseModel):
    """Respuesta de límite personalizado."""
    id: UUID
    card_id: UUID
    limit_type: str
    limit_identifier: str
    action: str
    daily_limit: Optional[Decimal]
    monthly_limit: Optional[Decimal]
    single_limit: Optional[Decimal]
    daily_used: Decimal
    monthly_used: Decimal
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CardLimitList(BaseModel):
    """Lista de límites personalizados."""
    limits: List[CardLimitResponse]
    total: int


# =====================
# Card Dispute Schemas
# =====================

class CardDisputeCreate(BaseModel):
    """Crear disputa de transacción."""
    transaction_id: UUID
    reason_code: str = Field(..., max_length=10)
    reason_description: str = Field(..., max_length=255)
    user_description: Optional[str] = None
    disputed_amount: Optional[Decimal] = Field(None, gt=0)
    documents: Optional[List[str]] = None


class CardDisputeResponse(BaseModel):
    """Respuesta de disputa."""
    id: UUID
    dispute_number: str
    transaction_id: UUID
    user_id: UUID
    reason_code: str
    reason_description: str
    user_description: Optional[str]
    disputed_amount: Decimal
    currency: str
    status: str
    resolution: Optional[str]
    resolution_date: Optional[datetime]
    provisional_credit_given: bool
    provisional_credit_amount: Optional[Decimal]
    provisional_credit_date: Optional[datetime]
    documents: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CardDisputeList(BaseModel):
    """Lista de disputas."""
    disputes: List[CardDisputeResponse]
    total: int
    open_count: int
    resolved_count: int


# =====================
# Card Reward Schemas
# =====================

class CardRewardResponse(BaseModel):
    """Respuesta de recompensa."""
    id: UUID
    user_id: UUID
    transaction_id: Optional[UUID]
    reward_type: str
    amount: Decimal
    currency: str
    description: Optional[str]
    category: Optional[str]
    status: str
    credited_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class CardRewardList(BaseModel):
    """Lista de recompensas."""
    rewards: List[CardRewardResponse]
    total: int
    total_pending: Decimal
    total_credited: Decimal
    total_expired: Decimal


class CardRewardsSummary(BaseModel):
    """Resumen de recompensas."""
    total_earned: Decimal
    total_pending: Decimal
    total_redeemed: Decimal
    current_balance: Decimal
    earning_rate: Decimal
    next_expiry: Optional[datetime]
    expiring_amount: Optional[Decimal]


# =====================
# Card Analytics Schemas
# =====================

class CardAnalytics(BaseModel):
    """Analíticas de tarjeta."""
    total_spent_month: Decimal
    total_spent_year: Decimal
    total_transactions: int
    average_transaction: Decimal
    spending_by_category: List[Dict[str, Any]]
    spending_by_merchant: List[Dict[str, Any]]
    spending_by_day: List[Dict[str, Any]]
    international_spending: Decimal
    online_spending: Decimal
    atm_withdrawals: Decimal
    rewards_earned: Decimal


class CardSecuritySummary(BaseModel):
    """Resumen de seguridad de tarjeta."""
    card_id: UUID
    status: CardStatus
    is_frozen: bool
    last_used_at: Optional[datetime]
    last_used_location: Optional[str]
    suspicious_transactions: int
    blocked_attempts: int
    active_limits: int
    international_enabled: bool
    online_enabled: bool
    contactless_enabled: bool
