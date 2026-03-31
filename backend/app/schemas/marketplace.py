"""
Schemas Pydantic para el Marketplace Secundario.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ==================== ENUMS ====================

class OrderSideEnum(str, Enum):
    """Lado de la orden."""
    BUY = "buy"
    SELL = "sell"


class OrderTypeEnum(str, Enum):
    """Tipo de orden."""
    LIMIT = "limit"
    MARKET = "market"


class OrderStatusEnum(str, Enum):
    """Estado de la orden."""
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ListingStatusEnum(str, Enum):
    """Estado del listing."""
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELISTED = "delisted"


# ==================== TOKEN LISTING SCHEMAS ====================

class TokenListingBase(BaseModel):
    """Base para listing de token."""
    min_order_amount: Decimal = Field(default=Decimal("1"), ge=0)
    max_order_amount: Optional[Decimal] = None
    price_tick_size: Decimal = Field(default=Decimal("0.01"), gt=0)
    maker_fee_percent: Decimal = Field(default=Decimal("0.001"), ge=0, le=1)
    taker_fee_percent: Decimal = Field(default=Decimal("0.002"), ge=0, le=1)
    daily_volume_limit: Optional[Decimal] = None


class TokenListingCreate(TokenListingBase):
    """Crear listing de token."""
    project_token_id: UUID


class TokenListingResponse(BaseModel):
    """Respuesta de listing."""
    id: UUID
    project_token_id: UUID
    status: str
    min_order_amount: Decimal
    max_order_amount: Optional[Decimal]
    price_tick_size: Decimal
    maker_fee_percent: Decimal
    taker_fee_percent: Decimal
    daily_volume_limit: Optional[Decimal]
    current_daily_volume: Decimal
    total_volume: Decimal
    total_trades: int
    total_fees_collected: Decimal
    listed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class MarketTokenInfo(BaseModel):
    """Información de token para el marketplace."""
    listing_id: UUID
    token_id: UUID
    token_symbol: str
    token_name: str
    project_id: UUID
    project_name: str

    # Precio actual
    current_price: Decimal
    price_change_24h: Optional[Decimal] = None
    price_change_percent_24h: Optional[Decimal] = None

    # Volumen
    volume_24h: Decimal
    volume_7d: Optional[Decimal] = None

    # Market cap
    market_cap: Decimal
    circulating_supply: Decimal
    total_supply: Decimal

    # Trading info
    total_trades: int
    status: str

    # Best bid/ask
    best_bid: Optional[Decimal] = None
    best_ask: Optional[Decimal] = None
    spread: Optional[Decimal] = None


# ==================== ORDER SCHEMAS ====================

class OrderCreate(BaseModel):
    """Crear orden de compra/venta."""
    listing_id: UUID
    side: OrderSideEnum
    order_type: OrderTypeEnum = OrderTypeEnum.LIMIT
    amount: Decimal = Field(..., gt=0, description="Cantidad de tokens")
    price: Optional[Decimal] = Field(
        None, gt=0, description="Precio por token (requerido para limit orders)"
    )
    wallet_id: Optional[UUID] = None
    expires_at: Optional[datetime] = None
    client_order_id: Optional[str] = Field(None, max_length=64)

    @field_validator('price')
    @classmethod
    def validate_price_for_limit(cls, v, info):
        if info.data.get('order_type') == OrderTypeEnum.LIMIT and v is None:
            raise ValueError('Price is required for limit orders')
        return v


class OrderUpdate(BaseModel):
    """Actualizar orden (solo precio para limit orders)."""
    price: Optional[Decimal] = Field(None, gt=0)


class OrderResponse(BaseModel):
    """Respuesta de orden."""
    id: UUID
    listing_id: UUID
    user_id: UUID
    wallet_id: Optional[UUID]
    side: str
    order_type: str
    amount: Decimal
    filled_amount: Decimal
    remaining_amount: Decimal
    price: Optional[Decimal]
    average_fill_price: Optional[Decimal]
    status: str
    estimated_fee: Decimal
    actual_fee: Decimal
    fill_percentage: float
    total_value: float
    expires_at: Optional[datetime]
    client_order_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    filled_at: Optional[datetime]
    cancelled_at: Optional[datetime]

    class Config:
        from_attributes = True


class OrderBookEntry(BaseModel):
    """Entrada en el orderbook."""
    price: Decimal
    amount: Decimal
    total: Decimal
    orders_count: int


class OrderBook(BaseModel):
    """Orderbook completo."""
    listing_id: UUID
    token_symbol: str
    bids: List[OrderBookEntry]  # Órdenes de compra (mayor a menor precio)
    asks: List[OrderBookEntry]  # Órdenes de venta (menor a mayor precio)
    spread: Optional[Decimal] = None
    spread_percent: Optional[Decimal] = None
    last_updated: datetime


class OrderCancelResponse(BaseModel):
    """Respuesta de cancelación de orden."""
    success: bool
    order_id: UUID
    status: str
    message: str


# ==================== TRADE SCHEMAS ====================

class TradeResponse(BaseModel):
    """Respuesta de trade ejecutado."""
    id: UUID
    listing_id: UUID
    token_symbol: str
    buyer_id: Optional[UUID]
    seller_id: Optional[UUID]
    amount: Decimal
    price: Decimal
    total_value: Decimal
    maker_fee: Decimal
    taker_fee: Decimal
    total_fee: Decimal
    is_settled_onchain: bool
    settlement_tx_hash: Optional[str]
    executed_at: datetime

    class Config:
        from_attributes = True


class TradeHistoryResponse(BaseModel):
    """Historial de trades."""
    trades: List[TradeResponse]
    total: int
    page: int
    page_size: int


class RecentTrade(BaseModel):
    """Trade reciente (para ticker)."""
    id: UUID
    price: Decimal
    amount: Decimal
    side: str  # buy/sell desde perspectiva del taker
    executed_at: datetime


# ==================== PRICE/MARKET DATA SCHEMAS ====================

class OHLCVData(BaseModel):
    """Datos OHLCV para gráficos."""
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trades_count: int
    vwap: Optional[Decimal] = None


class MarketDataResponse(BaseModel):
    """Datos de mercado completos."""
    listing_id: UUID
    token_symbol: str
    interval: str
    data: List[OHLCVData]


class TickerResponse(BaseModel):
    """Ticker de un token."""
    listing_id: UUID
    token_symbol: str
    token_name: str

    # Precios
    last_price: Decimal
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None

    # Cambio 24h
    price_change_24h: Decimal
    price_change_percent_24h: Decimal
    high_24h: Decimal
    low_24h: Decimal

    # Volumen
    volume_24h: Decimal
    volume_quote_24h: Decimal
    trades_24h: int

    timestamp: datetime


class AllTickersResponse(BaseModel):
    """Todos los tickers."""
    tickers: List[TickerResponse]
    last_updated: datetime


# ==================== USER TRADING STATS ====================

class UserTradingStatsResponse(BaseModel):
    """Estadísticas de trading del usuario."""
    user_id: UUID
    total_trades: int
    total_buy_volume: Decimal
    total_sell_volume: Decimal
    total_fees_paid: Decimal
    total_orders_placed: int
    total_orders_filled: int
    total_orders_cancelled: int
    realized_pnl: Decimal
    first_trade_at: Optional[datetime]
    last_trade_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserPortfolioItem(BaseModel):
    """Item del portfolio con opciones de venta."""
    token_id: UUID
    listing_id: Optional[UUID]
    token_symbol: str
    token_name: str
    balance: Decimal
    available_balance: Decimal
    locked_balance: Decimal
    average_cost: Decimal
    current_price: Decimal
    current_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_percent: Decimal
    is_tradeable: bool  # Si está listado en marketplace


class UserMarketplacePortfolio(BaseModel):
    """Portfolio del usuario para marketplace."""
    total_value: Decimal
    total_unrealized_pnl: Decimal
    items: List[UserPortfolioItem]


# ==================== MARKETPLACE SUMMARY ====================

class MarketplaceSummary(BaseModel):
    """Resumen del marketplace."""
    total_listings: int
    active_listings: int
    total_volume_24h: Decimal
    total_trades_24h: int
    total_volume_all_time: Decimal
    total_trades_all_time: int
    top_gainers: List[MarketTokenInfo]
    top_losers: List[MarketTokenInfo]
    most_traded: List[MarketTokenInfo]
    recently_listed: List[MarketTokenInfo]


# ==================== ORDER EXECUTION RESULT ====================

class OrderExecutionResult(BaseModel):
    """Resultado de ejecución de orden."""
    order: OrderResponse
    trades: List[TradeResponse]
    message: str
