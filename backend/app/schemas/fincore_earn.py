"""
Schemas para Fincore Earn - Productos de Rendimiento.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from enum import Enum


class EarnProductType(str, Enum):
    FLEXIBLE = "flexible"
    FIXED_30 = "fixed_30"
    FIXED_60 = "fixed_60"
    FIXED_90 = "fixed_90"
    FIXED_180 = "fixed_180"
    FIXED_365 = "fixed_365"
    STAKING = "staking"


class EarnProductStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    COMING_SOON = "coming_soon"


class EarnPositionStatus(str, Enum):
    ACTIVE = "active"
    PENDING_WITHDRAWAL = "pending_withdrawal"
    WITHDRAWN = "withdrawn"
    LIQUIDATED = "liquidated"


class EarnTransactionType(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    YIELD_PAYMENT = "yield_payment"
    COMPOUND = "compound"
    EARLY_WITHDRAWAL = "early_withdrawal"
    PENALTY = "penalty"
    BONUS = "bonus"


# =====================
# Product Schemas
# =====================

class EarnProductResponse(BaseModel):
    """Respuesta de producto Earn."""
    id: UUID
    code: str
    name: str
    description: Optional[str]
    product_type: EarnProductType
    status: EarnProductStatus
    currency: str
    is_crypto: bool

    # Rendimiento
    apy_base: Decimal
    apy_bonus: Optional[Decimal]
    apy_max: Optional[Decimal]
    current_apy: Decimal
    is_variable_rate: bool

    # Límites
    min_deposit: Decimal
    max_deposit: Optional[Decimal]
    total_capacity: Optional[Decimal]
    current_tvl: Decimal
    available_capacity: Optional[Decimal]

    # Plazo
    lock_period_days: int
    early_withdrawal_penalty: Decimal
    yield_frequency: str
    compound_enabled: bool

    # Riesgo
    risk_level: int
    risk_description: Optional[str]

    # UI
    icon_url: Optional[str]
    color: Optional[str]
    display_order: int

    # Promoción
    is_promoted: bool
    promotion_end_at: Optional[datetime]
    promotion_message: Optional[str]

    # Terms
    terms_url: Optional[str]

    created_at: datetime

    class Config:
        from_attributes = True


class EarnProductList(BaseModel):
    """Lista de productos Earn."""
    products: List[EarnProductResponse]
    total: int
    by_type: Dict[str, int]


# =====================
# Position Schemas
# =====================

class EarnPositionCreate(BaseModel):
    """Crear posición en producto Earn."""
    product_id: UUID
    amount: Decimal = Field(..., gt=0)
    auto_compound: bool = True
    auto_renew: bool = False
    promo_code: Optional[str] = Field(None, max_length=20)

    @validator("amount")
    def validate_amount(cls, v):
        if v.as_tuple().exponent < -8:
            raise ValueError("Máximo 8 decimales permitidos")
        return v


class EarnPositionResponse(BaseModel):
    """Respuesta de posición Earn."""
    id: UUID
    position_number: str
    user_id: UUID
    product_id: UUID

    # Montos
    principal: Decimal
    accrued_yield: Decimal
    total_withdrawn: Decimal
    compound_earnings: Decimal
    current_value: Decimal
    total_yield: Decimal
    currency: str

    # APY
    locked_apy: Optional[Decimal]

    # Estado
    status: EarnPositionStatus

    # Fechas
    start_date: datetime
    maturity_date: Optional[datetime]
    last_yield_date: Optional[datetime]
    is_mature: bool

    # Configuración
    auto_compound: bool
    auto_renew: bool
    renewal_count: int

    # Producto info
    product_name: Optional[str] = None
    product_type: Optional[str] = None

    created_at: datetime
    withdrawn_at: Optional[datetime]

    class Config:
        from_attributes = True


class EarnPositionList(BaseModel):
    """Lista de posiciones Earn."""
    positions: List[EarnPositionResponse]
    total: int
    total_value: Decimal
    total_yield: Decimal
    by_status: Dict[str, int]


class EarnPositionWithdraw(BaseModel):
    """Retirar de posición Earn."""
    amount: Optional[Decimal] = Field(None, gt=0)
    withdraw_all: bool = False
    withdraw_yield_only: bool = False

    @validator("withdraw_all")
    def validate_withdrawal(cls, v, values):
        amount = values.get("amount")
        yield_only = values.get("withdraw_yield_only", False)
        if not v and not amount and not yield_only:
            raise ValueError("Especifique monto, withdraw_all o withdraw_yield_only")
        return v


class EarnPositionUpdate(BaseModel):
    """Actualizar posición Earn."""
    auto_compound: Optional[bool] = None
    auto_renew: Optional[bool] = None


# =====================
# Transaction Schemas
# =====================

class EarnTransactionResponse(BaseModel):
    """Respuesta de transacción Earn."""
    id: UUID
    transaction_number: str
    position_id: UUID
    user_id: UUID
    transaction_type: EarnTransactionType
    amount: Decimal
    currency: str
    applied_apy: Optional[Decimal]
    calculation_days: Optional[int]
    balance_after: Optional[Decimal]
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class EarnTransactionList(BaseModel):
    """Lista de transacciones Earn."""
    transactions: List[EarnTransactionResponse]
    total: int
    page: int
    page_size: int


# =====================
# Yield Distribution Schemas
# =====================

class YieldDistributionResponse(BaseModel):
    """Respuesta de distribución de rendimiento."""
    id: UUID
    distribution_id: str
    position_id: UUID
    product_id: UUID
    user_id: UUID
    period_start: datetime
    period_end: datetime
    principal_amount: Decimal
    applied_apy: Decimal
    days_calculated: int
    gross_yield: Decimal
    fee: Decimal
    net_yield: Decimal
    currency: str
    is_compounded: bool
    is_withdrawn: bool
    status: str
    created_at: datetime
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True


class YieldDistributionList(BaseModel):
    """Lista de distribuciones."""
    distributions: List[YieldDistributionResponse]
    total: int
    total_yield: Decimal
    total_compounded: Decimal
    total_withdrawn: Decimal


# =====================
# Promotion Schemas
# =====================

class EarnPromotionResponse(BaseModel):
    """Respuesta de promoción Earn."""
    id: UUID
    code: str
    name: str
    description: Optional[str]
    promotion_type: str
    bonus_value: Decimal
    bonus_type: str
    applicable_products: List[str]
    min_deposit: Optional[Decimal]
    min_lock_days: Optional[int]
    start_date: datetime
    end_date: datetime
    is_active: bool
    is_available: bool = True

    class Config:
        from_attributes = True


class EarnPromotionApply(BaseModel):
    """Aplicar código promocional."""
    promo_code: str = Field(..., min_length=1, max_length=20)


class EarnPromotionValidation(BaseModel):
    """Validación de código promocional."""
    is_valid: bool
    promotion: Optional[EarnPromotionResponse]
    error_message: Optional[str]
    bonus_preview: Optional[Decimal]


# =====================
# Analytics Schemas
# =====================

class EarnAnalytics(BaseModel):
    """Analíticas de Earn."""
    total_deposited: Decimal
    total_yield_earned: Decimal
    total_withdrawn: Decimal
    current_balance: Decimal
    active_positions: int
    average_apy: Decimal
    yield_by_month: List[Dict[str, Any]]
    positions_by_product: List[Dict[str, Any]]
    yield_projections: Dict[str, Decimal]


class EarnSummary(BaseModel):
    """Resumen de Earn para dashboard."""
    total_balance: Decimal
    total_yield_today: Decimal
    total_yield_month: Decimal
    total_yield_all_time: Decimal
    active_positions: int
    best_performing_product: Optional[str]
    best_apy: Optional[Decimal]
    next_yield_payment: Optional[datetime]
    next_maturity: Optional[datetime]


# =====================
# Calculator Schemas
# =====================

class EarnCalculatorRequest(BaseModel):
    """Solicitud de cálculo de rendimiento."""
    product_id: UUID
    amount: Decimal = Field(..., gt=0)
    term_days: Optional[int] = None
    compound: bool = True


class EarnCalculatorResponse(BaseModel):
    """Respuesta de cálculo de rendimiento."""
    product_name: str
    initial_amount: Decimal
    term_days: int
    apy: Decimal

    # Proyecciones
    yield_daily: Decimal
    yield_monthly: Decimal
    yield_yearly: Decimal
    yield_at_maturity: Decimal

    # Con compound
    final_amount_simple: Decimal
    final_amount_compound: Decimal

    # Comparación
    compound_benefit: Decimal
