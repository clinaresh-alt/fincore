"""
Schemas para Préstamos con Colateral.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from enum import Enum


class LoanStatus(str, Enum):
    DRAFT = "draft"
    PENDING_COLLATERAL = "pending_collateral"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ACTIVE = "active"
    MARGIN_CALL = "margin_call"
    LIQUIDATING = "liquidating"
    LIQUIDATED = "liquidated"
    REPAID = "repaid"
    DEFAULTED = "defaulted"
    CANCELLED = "cancelled"


class CollateralType(str, Enum):
    CRYPTO = "crypto"
    TOKEN = "token"
    STABLECOIN = "stablecoin"
    NFT = "nft"


class CollateralStatus(str, Enum):
    PENDING = "pending"
    LOCKED = "locked"
    PARTIALLY_RELEASED = "partially_released"
    RELEASED = "released"
    LIQUIDATED = "liquidated"


class PaymentType(str, Enum):
    SCHEDULED = "scheduled"
    EARLY = "early"
    PARTIAL = "partial"
    FULL = "full"
    INTEREST_ONLY = "interest_only"
    LIQUIDATION = "liquidation"


# =====================
# Loan Product Schemas
# =====================

class LoanProductResponse(BaseModel):
    """Respuesta de producto de préstamo."""
    id: UUID
    code: str
    name: str
    description: Optional[str]
    is_active: bool
    loan_currency: str
    accepted_collaterals: List[str]

    # Tasas
    interest_rate_annual: Decimal
    interest_rate_monthly: Optional[Decimal]
    interest_type: str

    # LTV
    max_ltv: Decimal
    initial_ltv: Decimal
    margin_call_ltv: Decimal
    liquidation_ltv: Decimal

    # Límites
    min_loan_amount: Decimal
    max_loan_amount: Optional[Decimal]
    min_term_days: int
    max_term_days: int

    # Comisiones
    origination_fee_percent: Decimal
    early_repayment_fee_percent: Decimal
    late_payment_fee_percent: Decimal
    liquidation_fee_percent: Decimal

    # Frecuencia
    payment_frequency: str
    grace_period_days: int

    # KYC
    min_kyc_level: int

    # Terms
    terms_url: Optional[str]
    risk_disclosure: Optional[str]

    created_at: datetime

    class Config:
        from_attributes = True


class LoanProductList(BaseModel):
    """Lista de productos de préstamo."""
    products: List[LoanProductResponse]
    total: int


# =====================
# Loan Schemas
# =====================

class LoanCreate(BaseModel):
    """Crear préstamo."""
    product_id: UUID
    principal: Decimal = Field(..., gt=0)
    term_days: int = Field(..., ge=30, le=365)
    auto_repay_enabled: bool = False
    offer_code: Optional[str] = Field(None, max_length=20)

    @validator("principal")
    def validate_principal(cls, v):
        if v.as_tuple().exponent < -8:
            raise ValueError("Máximo 8 decimales permitidos")
        return v


class LoanResponse(BaseModel):
    """Respuesta de préstamo."""
    id: UUID
    loan_number: str
    user_id: UUID
    product_id: UUID

    # Monto
    principal: Decimal
    currency: str
    interest_rate: Decimal
    origination_fee: Decimal

    # Plazo
    term_days: int
    start_date: Optional[datetime]
    maturity_date: Optional[datetime]

    # Estado
    status: LoanStatus

    # Balances
    outstanding_principal: Optional[Decimal]
    accrued_interest: Decimal
    total_outstanding: Decimal
    total_paid: Decimal
    total_interest_paid: Decimal

    # Pagos
    next_payment_date: Optional[datetime]
    next_payment_amount: Optional[Decimal]
    payments_made: int
    payments_total: Optional[int]

    # LTV y Salud
    current_ltv: Optional[Decimal]
    last_ltv_update: Optional[datetime]
    total_collateral_value_usd: Decimal
    health_factor: Optional[Decimal]

    # Margin Call
    is_margin_call: bool
    margin_call_at: Optional[datetime]
    margin_call_deadline: Optional[datetime]

    # Configuración
    auto_repay_enabled: bool

    # Producto info
    product_name: Optional[str] = None
    product_code: Optional[str] = None

    # Timestamps
    created_at: datetime
    approved_at: Optional[datetime]
    disbursed_at: Optional[datetime]
    closed_at: Optional[datetime]

    class Config:
        from_attributes = True


class LoanList(BaseModel):
    """Lista de préstamos."""
    loans: List[LoanResponse]
    total: int
    total_outstanding: Decimal
    by_status: Dict[str, int]


class LoanSimulation(BaseModel):
    """Simulación de préstamo."""
    product_id: UUID
    principal: Decimal = Field(..., gt=0)
    term_days: int = Field(..., ge=30, le=365)
    collateral_asset: str
    collateral_amount: Decimal = Field(..., gt=0)


class LoanSimulationResponse(BaseModel):
    """Respuesta de simulación."""
    product_name: str
    principal: Decimal
    currency: str
    term_days: int

    # Tasas y comisiones
    interest_rate_annual: Decimal
    total_interest: Decimal
    origination_fee: Decimal
    total_cost: Decimal

    # Pagos
    payment_frequency: str
    number_of_payments: int
    payment_amount: Decimal

    # Colateral
    collateral_asset: str
    collateral_amount: Decimal
    collateral_value_usd: Decimal
    initial_ltv: Decimal

    # LTV thresholds
    margin_call_ltv: Decimal
    liquidation_ltv: Decimal

    # Precio de liquidación
    collateral_price_at_margin_call: Decimal
    collateral_price_at_liquidation: Decimal

    # Aprobación
    is_eligible: bool
    rejection_reasons: List[str]


# =====================
# Collateral Schemas
# =====================

class CollateralDeposit(BaseModel):
    """Depositar colateral."""
    loan_id: UUID
    collateral_type: CollateralType
    asset_symbol: str = Field(..., max_length=20)
    asset_network: Optional[str] = Field(None, max_length=20)
    amount: Decimal = Field(..., gt=0)

    @validator("amount")
    def validate_amount(cls, v):
        if v.as_tuple().exponent < -8:
            raise ValueError("Máximo 8 decimales permitidos")
        return v


class CollateralResponse(BaseModel):
    """Respuesta de colateral."""
    id: UUID
    loan_id: UUID
    user_id: UUID
    collateral_type: CollateralType
    asset_symbol: str
    asset_network: Optional[str]
    asset_contract: Optional[str]

    # Cantidades
    amount: Decimal
    amount_released: Decimal
    amount_liquidated: Decimal
    amount_locked: Decimal

    # Valores
    price_at_deposit: Decimal
    value_usd_at_deposit: Decimal
    current_price: Optional[Decimal]
    current_value_usd: Optional[Decimal]
    last_price_update: Optional[datetime]

    # Valor change
    value_change_percent: Optional[Decimal] = None

    # Estado
    status: CollateralStatus

    # Custodia
    custody_address: Optional[str]
    deposit_tx_hash: Optional[str]
    release_tx_hash: Optional[str]

    # Timestamps
    created_at: datetime
    locked_at: Optional[datetime]
    released_at: Optional[datetime]

    class Config:
        from_attributes = True


class CollateralList(BaseModel):
    """Lista de colaterales."""
    collaterals: List[CollateralResponse]
    total: int
    total_value_usd: Decimal
    by_asset: Dict[str, Decimal]


class CollateralRelease(BaseModel):
    """Solicitar liberación de colateral."""
    collateral_id: UUID
    amount: Optional[Decimal] = Field(None, gt=0)
    release_all: bool = False
    destination_address: Optional[str] = Field(None, max_length=100)

    @validator("release_all")
    def validate_release(cls, v, values):
        if not v and values.get("amount") is None:
            raise ValueError("Especifique monto o release_all")
        return v


# =====================
# Payment Schemas
# =====================

class LoanPaymentCreate(BaseModel):
    """Realizar pago de préstamo."""
    loan_id: UUID
    amount: Decimal = Field(..., gt=0)
    payment_type: PaymentType = PaymentType.SCHEDULED
    payment_method: str = Field(default="balance", regex=r"^(balance|bank_transfer|crypto)$")

    @validator("amount")
    def validate_amount(cls, v):
        if v.as_tuple().exponent < -8:
            raise ValueError("Máximo 8 decimales permitidos")
        return v


class LoanPaymentResponse(BaseModel):
    """Respuesta de pago."""
    id: UUID
    payment_number: str
    loan_id: UUID
    user_id: UUID
    payment_type: PaymentType

    # Montos
    total_amount: Decimal
    principal_amount: Decimal
    interest_amount: Decimal
    fee_amount: Decimal
    currency: str

    # Balance después
    principal_after: Optional[Decimal]
    interest_after: Optional[Decimal]

    # Cuota
    installment_number: Optional[int]
    scheduled_date: Optional[datetime]
    is_late: bool
    days_late: int

    # Método
    payment_method: Optional[str]
    payment_reference: Optional[str]

    # Estado
    status: str

    # Timestamps
    created_at: datetime
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True


class LoanPaymentList(BaseModel):
    """Lista de pagos."""
    payments: List[LoanPaymentResponse]
    total: int
    total_paid: Decimal
    total_principal_paid: Decimal
    total_interest_paid: Decimal


class PaymentSchedule(BaseModel):
    """Calendario de pagos."""
    loan_id: UUID
    loan_number: str
    payments: List[Dict[str, Any]]
    total_principal: Decimal
    total_interest: Decimal
    total_amount: Decimal


# =====================
# Liquidation Schemas
# =====================

class LiquidationEventResponse(BaseModel):
    """Respuesta de evento de liquidación."""
    id: UUID
    liquidation_id: str
    loan_id: UUID
    user_id: UUID

    # Trigger
    trigger_reason: str
    trigger_ltv: Optional[Decimal]
    trigger_health_factor: Optional[Decimal]

    # Deuda
    outstanding_debt: Decimal
    debt_currency: str

    # Colateral
    collateral_asset: str
    collateral_amount: Decimal
    collateral_price: Decimal
    collateral_value_usd: Decimal

    # Resultados
    debt_repaid: Optional[Decimal]
    liquidation_fee: Optional[Decimal]
    surplus_returned: Optional[Decimal]

    # Ejecución
    status: str
    execution_price: Optional[Decimal]
    execution_tx_hash: Optional[str]

    # Timestamps
    created_at: datetime
    executed_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class LiquidationEventList(BaseModel):
    """Lista de liquidaciones."""
    events: List[LiquidationEventResponse]
    total: int
    total_liquidated: Decimal


# =====================
# Loan Offer Schemas
# =====================

class LoanOfferResponse(BaseModel):
    """Respuesta de oferta de préstamo."""
    id: UUID
    offer_code: str
    user_id: UUID
    product_id: UUID
    max_amount: Decimal
    interest_rate: Decimal
    max_term_days: Optional[int]
    special_conditions: Dict[str, Any]
    message: Optional[str]
    valid_from: datetime
    valid_until: datetime
    is_active: bool
    is_used: bool
    used_at: Optional[datetime]

    # Producto info
    product_name: Optional[str] = None

    created_at: datetime

    class Config:
        from_attributes = True


class LoanOfferList(BaseModel):
    """Lista de ofertas."""
    offers: List[LoanOfferResponse]
    total: int
    active_count: int


class LoanOfferAccept(BaseModel):
    """Aceptar oferta de préstamo."""
    amount: Decimal = Field(..., gt=0)
    term_days: int = Field(..., ge=30, le=365)


# =====================
# Analytics Schemas
# =====================

class LendingAnalytics(BaseModel):
    """Analíticas de préstamos."""
    total_borrowed: Decimal
    total_outstanding: Decimal
    total_paid: Decimal
    total_interest_paid: Decimal
    active_loans: int
    average_interest_rate: Decimal
    total_collateral_value: Decimal
    average_ltv: Decimal
    payment_history: List[Dict[str, Any]]
    ltv_history: List[Dict[str, Any]]


class LendingSummary(BaseModel):
    """Resumen de préstamos para dashboard."""
    active_loans: int
    total_outstanding: Decimal
    next_payment_date: Optional[datetime]
    next_payment_amount: Optional[Decimal]
    total_collateral_value: Decimal
    average_health_factor: Optional[Decimal]
    loans_at_risk: int
    available_credit: Decimal


# =====================
# Health Check Schemas
# =====================

class LoanHealthCheck(BaseModel):
    """Verificación de salud de préstamo."""
    loan_id: UUID
    loan_number: str
    status: LoanStatus
    current_ltv: Decimal
    margin_call_ltv: Decimal
    liquidation_ltv: Decimal
    health_factor: Decimal
    health_status: str  # healthy, warning, critical
    ltv_buffer_to_margin_call: Decimal
    ltv_buffer_to_liquidation: Decimal
    collateral_drop_to_margin_call: Decimal
    collateral_drop_to_liquidation: Decimal
    recommendations: List[str]


class PortfolioHealthCheck(BaseModel):
    """Verificación de salud de portfolio."""
    total_loans: int
    healthy_loans: int
    warning_loans: int
    critical_loans: int
    average_health_factor: Decimal
    total_collateral_value: Decimal
    total_debt: Decimal
    overall_ltv: Decimal
    loans: List[LoanHealthCheck]
