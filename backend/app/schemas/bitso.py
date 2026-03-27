"""
Schemas Pydantic para integracion con Bitso Exchange.

Bitso es el exchange de criptomonedas mas grande de Mexico y LATAM.
Permite conversion cripto-fiat y retiros directos a cuentas bancarias.

Documentacion API: https://bitso.com/api_info

Funcionalidades:
- Trading de criptomonedas (USDC, BTC, ETH, etc.)
- Conversion a MXN en tiempo real
- Retiros SPEI a cualquier banco mexicano
- Depositos y retiros de cripto
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum


# ============ Enums ============

class BitsoOrderSide(str, Enum):
    """Lado de la orden (compra/venta)."""
    BUY = "buy"
    SELL = "sell"


class BitsoOrderType(str, Enum):
    """Tipo de orden."""
    MARKET = "market"       # Ejecutar al mejor precio disponible
    LIMIT = "limit"         # Ejecutar a precio especifico


class BitsoOrderStatus(str, Enum):
    """Estado de orden."""
    OPEN = "open"           # Abierta (parcialmente ejecutada)
    COMPLETED = "completed" # Completamente ejecutada
    CANCELLED = "cancelled" # Cancelada
    PARTIALLY_FILLED = "partially_filled"


class BitsoWithdrawalStatus(str, Enum):
    """Estado de retiro."""
    PENDING = "pending"     # Pendiente de procesamiento
    PROCESSING = "processing"  # En proceso
    COMPLETE = "complete"   # Completado
    FAILED = "failed"       # Fallido
    CANCELLED = "cancelled" # Cancelado


class BitsoFundingStatus(str, Enum):
    """Estado de deposito."""
    PENDING = "pending"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class BitsoCurrency(str, Enum):
    """Monedas soportadas en Bitso."""
    MXN = "mxn"
    USD = "usd"
    BTC = "btc"
    ETH = "eth"
    USDC = "usdc"
    USDT = "usdt"
    DAI = "dai"
    XRP = "xrp"
    LTC = "ltc"
    MANA = "mana"


class BitsoBook(str, Enum):
    """Libros de ordenes disponibles."""
    BTC_MXN = "btc_mxn"
    ETH_MXN = "eth_mxn"
    USDC_MXN = "usdc_mxn"
    USDT_MXN = "usdt_mxn"
    DAI_MXN = "dai_mxn"
    XRP_MXN = "xrp_mxn"
    # USD pairs
    BTC_USD = "btc_usd"
    ETH_USD = "eth_usd"


# ============ Response Models (from Bitso API) ============

class BitsoTicker(BaseModel):
    """Ticker de un libro de ordenes."""
    book: str
    volume: Decimal = Field(..., description="Volumen 24h")
    high: Decimal = Field(..., description="Precio maximo 24h")
    low: Decimal = Field(..., description="Precio minimo 24h")
    last: Decimal = Field(..., description="Ultimo precio")
    bid: Decimal = Field(..., description="Mejor precio de compra")
    ask: Decimal = Field(..., description="Mejor precio de venta")
    vwap: Optional[Decimal] = Field(None, description="Precio promedio ponderado por volumen")
    created_at: Optional[datetime] = None

    @property
    def spread(self) -> Decimal:
        """Diferencia entre ask y bid."""
        return self.ask - self.bid

    @property
    def spread_percentage(self) -> Decimal:
        """Spread como porcentaje del precio medio."""
        mid = (self.ask + self.bid) / 2
        return (self.spread / mid) * 100 if mid > 0 else Decimal("0")

    class Config:
        from_attributes = True


class BitsoBalance(BaseModel):
    """Balance de una moneda en Bitso."""
    currency: str
    total: Decimal = Field(..., description="Balance total")
    available: Decimal = Field(..., description="Balance disponible para operar")
    locked: Decimal = Field(..., description="Balance bloqueado en ordenes")
    pending_deposit: Optional[Decimal] = Field(None, description="Depositos pendientes")
    pending_withdrawal: Optional[Decimal] = Field(None, description="Retiros pendientes")

    class Config:
        from_attributes = True


class BitsoAccountStatus(BaseModel):
    """Estado de la cuenta Bitso."""
    client_id: str
    first_name: str
    last_name: str
    status: str
    daily_limit: Decimal = Field(..., description="Limite diario MXN")
    monthly_limit: Decimal = Field(..., description="Limite mensual MXN")
    daily_remaining: Decimal
    monthly_remaining: Decimal
    cellphone_number: Optional[str] = None
    email: str
    is_verified: bool = False

    class Config:
        from_attributes = True


class BitsoOrder(BaseModel):
    """Orden de compra/venta."""
    oid: str = Field(..., description="Order ID")
    book: str
    side: BitsoOrderSide
    type: BitsoOrderType
    status: BitsoOrderStatus
    original_amount: Decimal
    unfilled_amount: Decimal
    price: Optional[Decimal] = None  # None para ordenes market
    created_at: datetime
    updated_at: Optional[datetime] = None

    @property
    def filled_amount(self) -> Decimal:
        """Cantidad ejecutada."""
        return self.original_amount - self.unfilled_amount

    @property
    def fill_percentage(self) -> Decimal:
        """Porcentaje ejecutado."""
        if self.original_amount == 0:
            return Decimal("0")
        return (self.filled_amount / self.original_amount) * 100

    class Config:
        from_attributes = True


class BitsoWithdrawal(BaseModel):
    """Retiro de fondos."""
    wid: str = Field(..., description="Withdrawal ID")
    status: BitsoWithdrawalStatus
    currency: str
    method: str = Field(..., description="Metodo: spei, crypto, etc.")
    amount: Decimal
    fee: Optional[Decimal] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    # Para retiros SPEI
    clabe: Optional[str] = None
    beneficiary_name: Optional[str] = None
    numeric_reference: Optional[str] = None
    tracking_code: Optional[str] = None

    # Para retiros crypto
    address: Optional[str] = None
    tx_hash: Optional[str] = None

    class Config:
        from_attributes = True


class BitsoFunding(BaseModel):
    """Deposito de fondos."""
    fid: str = Field(..., description="Funding ID")
    status: BitsoFundingStatus
    currency: str
    method: str
    amount: Decimal
    fee: Optional[Decimal] = None
    created_at: datetime
    details: Optional[Dict[str, Any]] = None

    # Para depositos crypto
    address: Optional[str] = None
    tx_hash: Optional[str] = None

    class Config:
        from_attributes = True


class BitsoTrade(BaseModel):
    """Trade ejecutado."""
    tid: str = Field(..., description="Trade ID")
    book: str
    side: BitsoOrderSide
    major: Decimal = Field(..., description="Cantidad de moneda mayor (BTC, ETH, etc.)")
    minor: Decimal = Field(..., description="Cantidad de moneda menor (MXN, USD)")
    price: Decimal
    fees_amount: Decimal
    fees_currency: str
    created_at: datetime
    oid: Optional[str] = None  # Order ID asociada

    class Config:
        from_attributes = True


# ============ Request Schemas ============

class PlaceOrderRequest(BaseModel):
    """Solicitud para colocar una orden."""
    book: BitsoBook = Field(..., description="Libro de ordenes (ej: usdc_mxn)")
    side: BitsoOrderSide = Field(..., description="buy o sell")
    type: BitsoOrderType = Field(BitsoOrderType.MARKET)
    major: Optional[Decimal] = Field(None, description="Cantidad en moneda mayor")
    minor: Optional[Decimal] = Field(None, description="Cantidad en moneda menor")
    price: Optional[Decimal] = Field(None, description="Precio (solo para limit)")

    @field_validator('major', 'minor')
    @classmethod
    def validate_amounts(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Cantidad debe ser mayor a cero')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "book": "usdc_mxn",
                "side": "sell",
                "type": "market",
                "major": 100.0
            }
        }


class SPEIWithdrawalRequest(BaseModel):
    """Solicitud de retiro SPEI."""
    amount: Decimal = Field(..., gt=0, description="Monto en MXN")
    clabe: str = Field(..., min_length=18, max_length=18, description="CLABE destino")
    beneficiary_name: str = Field(..., min_length=1, max_length=40)
    notes_ref: Optional[str] = Field(None, max_length=40, description="Referencia/Concepto")
    numeric_reference: Optional[str] = Field(None, max_length=7, description="Referencia numerica")

    @field_validator('clabe')
    @classmethod
    def validate_clabe(cls, v):
        if not v.isdigit():
            raise ValueError('CLABE debe contener solo digitos')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "amount": 15000.50,
                "clabe": "012180015678912345",
                "beneficiary_name": "JUAN PEREZ GARCIA",
                "notes_ref": "PAGO REMESA FRC-123"
            }
        }


class CryptoWithdrawalRequest(BaseModel):
    """Solicitud de retiro crypto."""
    currency: BitsoCurrency = Field(..., description="Moneda (usdc, btc, etc.)")
    amount: Decimal = Field(..., gt=0)
    address: str = Field(..., min_length=20, description="Direccion destino")
    tag: Optional[str] = Field(None, description="Tag/Memo (para XRP, etc.)")
    network: Optional[str] = Field(None, description="Red (polygon, ethereum, etc.)")

    class Config:
        json_schema_extra = {
            "example": {
                "currency": "usdc",
                "amount": 100.0,
                "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16",
                "network": "polygon"
            }
        }


class ConvertRequest(BaseModel):
    """Solicitud de conversion cripto-fiat."""
    from_currency: BitsoCurrency
    to_currency: BitsoCurrency
    amount: Decimal = Field(..., gt=0)

    class Config:
        json_schema_extra = {
            "example": {
                "from_currency": "usdc",
                "to_currency": "mxn",
                "amount": 500.0
            }
        }


# ============ Response Schemas ============

class ConvertResponse(BaseModel):
    """Respuesta de conversion."""
    success: bool
    order_id: Optional[str] = None
    from_currency: str
    to_currency: str
    from_amount: Decimal
    to_amount: Decimal
    rate: Decimal
    fee: Decimal
    created_at: datetime
    error: Optional[str] = None

    class Config:
        from_attributes = True


class QuoteResponse(BaseModel):
    """Cotizacion para conversion."""
    from_currency: str
    to_currency: str
    amount: Decimal
    rate: Decimal
    inverse_rate: Decimal
    result_amount: Decimal
    fee: Decimal
    fee_percentage: Decimal
    expires_at: datetime
    quote_id: Optional[str] = None

    class Config:
        from_attributes = True


class WithdrawalResponse(BaseModel):
    """Respuesta de retiro."""
    success: bool
    wid: Optional[str] = None
    status: Optional[BitsoWithdrawalStatus] = None
    amount: Decimal
    fee: Decimal
    currency: str
    method: str
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DepositAddressResponse(BaseModel):
    """Direccion de deposito crypto."""
    currency: str
    network: str
    address: str
    tag: Optional[str] = None  # Para XRP, etc.
    qr_code_url: Optional[str] = None

    class Config:
        from_attributes = True


# ============ Webhook Schemas ============

class BitsoWebhookPayload(BaseModel):
    """Payload de webhook de Bitso."""
    type: str = Field(..., description="Tipo de evento")
    payload: Dict[str, Any]
    created_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "type": "withdrawal.complete",
                "payload": {
                    "wid": "abc123",
                    "status": "complete",
                    "amount": "1500.00"
                },
                "created_at": "2024-01-15T10:30:00Z"
            }
        }


class BitsoWebhookWithdrawal(BaseModel):
    """Webhook de retiro."""
    wid: str
    status: BitsoWithdrawalStatus
    currency: str
    amount: Decimal
    method: str
    created_at: datetime


class BitsoWebhookFunding(BaseModel):
    """Webhook de deposito."""
    fid: str
    status: BitsoFundingStatus
    currency: str
    amount: Decimal
    method: str
    tx_hash: Optional[str] = None
    created_at: datetime


# ============ Internal Models ============

class BitsoCredentials(BaseModel):
    """Credenciales de API Bitso."""
    api_key: str
    api_secret: str

    class Config:
        # No mostrar en logs
        json_schema_extra = {"sensitive": True}


class BitsoRateCache(BaseModel):
    """Cache de tasa de cambio."""
    book: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    cached_at: datetime
    ttl_seconds: int = 30

    @property
    def is_expired(self) -> bool:
        from datetime import timedelta
        return datetime.utcnow() > self.cached_at + timedelta(seconds=self.ttl_seconds)

    @property
    def mid_price(self) -> Decimal:
        return (self.bid + self.ask) / 2


# ============ Constants ============

# Comisiones de Bitso (pueden cambiar)
BITSO_FEES = {
    "trading": Decimal("0.0065"),       # 0.65% comision de trading
    "spei_withdrawal": Decimal("0"),    # SPEI gratis en Bitso
    "crypto_withdrawal": {
        "usdc": Decimal("1"),           # 1 USDC
        "usdt": Decimal("1"),           # 1 USDT
        "btc": Decimal("0.0001"),       # 0.0001 BTC
        "eth": Decimal("0.005"),        # 0.005 ETH
    }
}

# Limites minimos de orden
BITSO_MIN_ORDER = {
    "usdc_mxn": Decimal("1"),           # 1 USDC minimo
    "btc_mxn": Decimal("0.00001"),      # 0.00001 BTC minimo
    "eth_mxn": Decimal("0.0001"),       # 0.0001 ETH minimo
}

# Minimo de retiro SPEI
BITSO_MIN_SPEI_WITHDRAWAL = Decimal("10")  # 10 MXN minimo
