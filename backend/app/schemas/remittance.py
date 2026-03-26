"""
Schemas Pydantic para el modulo de Remesas.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from enum import Enum


# ============ Enums ============

class CurrencyEnum(str, Enum):
    MXN = "MXN"
    USD = "USD"
    EUR = "EUR"
    CLP = "CLP"
    COP = "COP"
    PEN = "PEN"
    BRL = "BRL"
    ARS = "ARS"


class StablecoinEnum(str, Enum):
    USDC = "USDC"
    USDT = "USDT"
    DAI = "DAI"


class PaymentMethodEnum(str, Enum):
    SPEI = "spei"
    WIRE_TRANSFER = "wire_transfer"
    CARD = "card"
    CASH = "cash"
    CRYPTO = "crypto"


class DisbursementMethodEnum(str, Enum):
    BANK_TRANSFER = "bank_transfer"
    MOBILE_WALLET = "mobile_wallet"
    CASH_PICKUP = "cash_pickup"
    HOME_DELIVERY = "home_delivery"


class RemittanceStatusEnum(str, Enum):
    INITIATED = "initiated"
    PENDING_DEPOSIT = "pending_deposit"
    DEPOSITED = "deposited"
    LOCKED = "locked"
    PROCESSING = "processing"
    DISBURSED = "disbursed"
    COMPLETED = "completed"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


# ============ Request Schemas ============

class RecipientInfoSchema(BaseModel):
    """Informacion del beneficiario."""
    name: str = Field(..., min_length=2, max_length=100)
    bank_name: Optional[str] = Field(None, max_length=100)
    account_number: Optional[str] = Field(None, max_length=50)
    account_type: Optional[str] = Field(None, max_length=20)  # checking, savings
    clabe: Optional[str] = Field(None, min_length=18, max_length=18)  # Mexico
    iban: Optional[str] = Field(None, max_length=34)  # Internacional
    swift: Optional[str] = Field(None, max_length=11)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=2)  # ISO 3166-1 alpha-2

    @field_validator('clabe')
    @classmethod
    def validate_clabe(cls, v):
        if v and not v.isdigit():
            raise ValueError('CLABE debe contener solo digitos')
        return v


class QuoteRequest(BaseModel):
    """Solicitud de cotizacion."""
    amount_source: Decimal = Field(..., gt=0, description="Monto en moneda origen")
    currency_source: CurrencyEnum = Field(..., description="Moneda origen")
    currency_destination: CurrencyEnum = Field(..., description="Moneda destino")


class CreateRemittanceRequest(BaseModel):
    """Solicitud para crear una remesa."""
    recipient_info: RecipientInfoSchema
    amount_source: Decimal = Field(..., gt=10, le=10000, description="Monto a enviar")
    currency_source: CurrencyEnum
    currency_destination: CurrencyEnum
    payment_method: PaymentMethodEnum
    disbursement_method: DisbursementMethodEnum
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator('amount_source')
    @classmethod
    def validate_amount(cls, v):
        if v < 10:
            raise ValueError('Monto minimo es 10 USD equivalente')
        if v > 10000:
            raise ValueError('Monto maximo es 10,000 USD equivalente')
        return v


class LockFundsRequest(BaseModel):
    """Solicitud para bloquear fondos en escrow."""
    wallet_address: str = Field(..., min_length=42, max_length=42)

    @field_validator('wallet_address')
    @classmethod
    def validate_address(cls, v):
        if not v.startswith('0x'):
            raise ValueError('Direccion debe empezar con 0x')
        return v


class ReleaseFundsRequest(BaseModel):
    """Solicitud para liberar fondos (solo operadores)."""
    confirmation_code: Optional[str] = Field(None, description="Codigo de confirmacion de entrega")
    notes: Optional[str] = Field(None, max_length=500)


# ============ Response Schemas ============

class QuoteResponse(BaseModel):
    """Respuesta de cotizacion."""
    quote_id: str
    amount_source: Decimal
    currency_source: CurrencyEnum
    amount_destination: Decimal
    currency_destination: CurrencyEnum
    amount_stablecoin: Decimal
    exchange_rate_source_usd: Decimal
    exchange_rate_usd_destination: Decimal
    platform_fee: Decimal
    network_fee: Decimal
    total_fees: Decimal
    total_to_pay: Decimal
    estimated_delivery: datetime
    quote_expires_at: datetime

    class Config:
        from_attributes = True


class RemittanceResponse(BaseModel):
    """Respuesta con datos de remesa."""
    id: str
    reference_code: str
    status: RemittanceStatusEnum
    recipient_info: Dict[str, Any]
    amount_fiat_source: Decimal
    currency_source: CurrencyEnum
    amount_fiat_destination: Optional[Decimal]
    currency_destination: CurrencyEnum
    amount_stablecoin: Optional[Decimal]
    stablecoin: StablecoinEnum
    exchange_rate_source_usd: Optional[Decimal]
    platform_fee: Decimal
    network_fee: Decimal
    total_fees: Decimal
    payment_method: PaymentMethodEnum
    disbursement_method: DisbursementMethodEnum
    escrow_locked_at: Optional[datetime]
    escrow_expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class RemittanceListResponse(BaseModel):
    """Lista de remesas con paginacion."""
    items: List[RemittanceResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class RemittanceCreatedResponse(BaseModel):
    """Respuesta al crear una remesa."""
    success: bool
    remittance_id: Optional[str]
    reference_code: Optional[str]
    status: Optional[RemittanceStatusEnum]
    message: str
    next_steps: List[str]


class TransactionResponse(BaseModel):
    """Respuesta de transaccion blockchain."""
    success: bool
    tx_hash: Optional[str]
    status: Optional[str]
    error: Optional[str]


class ReconciliationLogResponse(BaseModel):
    """Respuesta de log de conciliacion."""
    id: str
    check_timestamp: datetime
    expected_balance_ledger: Decimal
    actual_balance_ledger: Decimal
    expected_balance_onchain: Decimal
    actual_balance_onchain: Decimal
    discrepancy_detected: bool
    discrepancy_onchain: Decimal
    network: str
    stablecoin: str
    error_payload: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class RemittanceLimitResponse(BaseModel):
    """Limites de remesa por nivel KYC."""
    kyc_level: int
    min_amount_usd: Decimal
    max_amount_usd: Decimal
    daily_limit_usd: Decimal
    monthly_limit_usd: Decimal
    current_daily_used: Decimal
    current_monthly_used: Decimal
    available_daily: Decimal
    available_monthly: Decimal


class ExchangeRateResponse(BaseModel):
    """Tasa de cambio."""
    currency_from: CurrencyEnum
    currency_to: CurrencyEnum
    rate: Decimal
    source: str
    captured_at: datetime
