"""
Modelos para el Marketplace Secundario de FinCore.
Sistema de trading P2P para tokens de inversión.
"""
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey,
    Numeric, Text, Enum as SQLEnum, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.core.database import Base
from app.models.blockchain import BlockchainNetwork


class OrderSide(str, enum.Enum):
    """Lado de la orden."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, enum.Enum):
    """Tipo de orden."""
    LIMIT = "limit"  # Orden con precio específico
    MARKET = "market"  # Orden a precio de mercado


class OrderStatus(str, enum.Enum):
    """Estado de la orden."""
    OPEN = "open"  # Activa en el orderbook
    PARTIALLY_FILLED = "partially_filled"  # Parcialmente ejecutada
    FILLED = "filled"  # Completamente ejecutada
    CANCELLED = "cancelled"  # Cancelada por usuario
    EXPIRED = "expired"  # Expirada


class ListingStatus(str, enum.Enum):
    """Estado del listing en marketplace."""
    PENDING = "pending"  # Pendiente de aprobación
    ACTIVE = "active"  # Activo para trading
    SUSPENDED = "suspended"  # Suspendido temporalmente
    DELISTED = "delisted"  # Removido del marketplace


class TokenListing(Base):
    """
    Listing de un token en el marketplace.
    Define qué tokens están disponibles para trading.
    """
    __tablename__ = "marketplace_listings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_token_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project_tokens.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    # Estado del listing
    status = Column(
        SQLEnum(ListingStatus, name="listing_status_enum", create_type=False),
        default=ListingStatus.PENDING
    )

    # Configuración de trading
    min_order_amount = Column(Numeric(28, 8), default=1)  # Mínimo por orden
    max_order_amount = Column(Numeric(28, 8), nullable=True)  # Máximo por orden (null = sin límite)
    price_tick_size = Column(Numeric(18, 8), default=0.01)  # Incremento mínimo de precio

    # Fees de trading (porcentaje)
    maker_fee_percent = Column(Numeric(5, 4), default=0.001)  # 0.1% maker fee
    taker_fee_percent = Column(Numeric(5, 4), default=0.002)  # 0.2% taker fee

    # Límites diarios
    daily_volume_limit = Column(Numeric(28, 8), nullable=True)  # Límite de volumen diario
    current_daily_volume = Column(Numeric(28, 8), default=0)
    volume_reset_at = Column(DateTime(timezone=True), nullable=True)

    # Estadísticas
    total_volume = Column(Numeric(28, 8), default=0)
    total_trades = Column(Integer, default=0)
    total_fees_collected = Column(Numeric(18, 8), default=0)

    # Timestamps
    listed_at = Column(DateTime(timezone=True), nullable=True)
    suspended_at = Column(DateTime(timezone=True), nullable=True)
    delisted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Metadata
    listing_reason = Column(Text, nullable=True)
    suspension_reason = Column(Text, nullable=True)

    # Relaciones
    project_token = relationship("ProjectToken", backref="marketplace_listing")
    orders = relationship("TokenOrder", back_populates="listing", cascade="all, delete-orphan")
    trades = relationship("TokenTrade", back_populates="listing", cascade="all, delete-orphan")
    price_history = relationship("MarketPrice", back_populates="listing", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_listing_status", "status"),
        Index("idx_listing_token", "project_token_id"),
    )


class TokenOrder(Base):
    """
    Orden de compra/venta en el marketplace.
    Sistema de orderbook para matching.
    """
    __tablename__ = "marketplace_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_listings.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )
    wallet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_wallets.id", ondelete="SET NULL"),
        nullable=True
    )

    # Tipo de orden
    side = Column(
        SQLEnum(OrderSide, name="order_side_enum", create_type=False),
        nullable=False
    )
    order_type = Column(
        SQLEnum(OrderType, name="order_type_enum", create_type=False),
        default=OrderType.LIMIT
    )

    # Cantidades
    amount = Column(Numeric(28, 8), nullable=False)  # Cantidad total de tokens
    filled_amount = Column(Numeric(28, 8), default=0)  # Cantidad ya ejecutada
    remaining_amount = Column(Numeric(28, 8), nullable=False)  # Cantidad pendiente

    # Precio
    price = Column(Numeric(18, 8), nullable=True)  # Precio por token (null para market orders)
    average_fill_price = Column(Numeric(18, 8), nullable=True)  # Precio promedio de ejecución

    # Estado
    status = Column(
        SQLEnum(OrderStatus, name="order_status_enum", create_type=False),
        default=OrderStatus.OPEN
    )

    # Fees
    estimated_fee = Column(Numeric(18, 8), default=0)
    actual_fee = Column(Numeric(18, 8), default=0)

    # Expiración
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Null = GTC (Good Till Cancelled)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    filled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    client_order_id = Column(String(64), nullable=True)  # ID del cliente para tracking
    cancellation_reason = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Relaciones
    listing = relationship("TokenListing", back_populates="orders")
    user = relationship("User", backref="marketplace_orders")
    wallet = relationship("UserWallet", backref="marketplace_orders")
    trades_as_maker = relationship(
        "TokenTrade",
        back_populates="maker_order",
        foreign_keys="TokenTrade.maker_order_id"
    )
    trades_as_taker = relationship(
        "TokenTrade",
        back_populates="taker_order",
        foreign_keys="TokenTrade.taker_order_id"
    )

    __table_args__ = (
        Index("idx_order_listing", "listing_id"),
        Index("idx_order_user", "user_id"),
        Index("idx_order_status", "status"),
        Index("idx_order_side_price", "listing_id", "side", "price"),  # Para matching
        Index("idx_order_created", "created_at"),
        CheckConstraint("amount > 0", name="positive_amount"),
        CheckConstraint("remaining_amount >= 0", name="non_negative_remaining"),
        CheckConstraint("filled_amount >= 0", name="non_negative_filled"),
        CheckConstraint(
            "price > 0 OR order_type = 'market'",
            name="price_required_for_limit"
        ),
    )

    @property
    def fill_percentage(self) -> float:
        """Porcentaje de la orden ejecutada."""
        if self.amount == 0:
            return 0
        return float(self.filled_amount / self.amount * 100)

    @property
    def total_value(self) -> float:
        """Valor total de la orden."""
        if self.price:
            return float(self.amount * self.price)
        return 0


class TokenTrade(Base):
    """
    Trade ejecutado entre dos órdenes.
    Registro inmutable de transacciones completadas.
    """
    __tablename__ = "marketplace_trades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_listings.id", ondelete="CASCADE"),
        nullable=False
    )

    # Órdenes involucradas
    maker_order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_orders.id", ondelete="SET NULL"),
        nullable=True
    )
    taker_order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_orders.id", ondelete="SET NULL"),
        nullable=True
    )

    # Usuarios
    buyer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    # Detalles del trade
    amount = Column(Numeric(28, 8), nullable=False)  # Cantidad de tokens
    price = Column(Numeric(18, 8), nullable=False)  # Precio por token
    total_value = Column(Numeric(28, 8), nullable=False)  # amount * price

    # Fees
    maker_fee = Column(Numeric(18, 8), default=0)
    taker_fee = Column(Numeric(18, 8), default=0)
    total_fee = Column(Numeric(18, 8), default=0)

    # Blockchain (opcional - para settlement on-chain)
    is_settled_onchain = Column(Boolean, default=False)
    settlement_tx_hash = Column(String(66), nullable=True)
    settlement_block = Column(Integer, nullable=True)

    # Timestamps
    executed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    settled_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    listing = relationship("TokenListing", back_populates="trades")
    maker_order = relationship(
        "TokenOrder",
        back_populates="trades_as_maker",
        foreign_keys=[maker_order_id]
    )
    taker_order = relationship(
        "TokenOrder",
        back_populates="trades_as_taker",
        foreign_keys=[taker_order_id]
    )
    buyer = relationship("User", foreign_keys=[buyer_id], backref="trades_as_buyer")
    seller = relationship("User", foreign_keys=[seller_id], backref="trades_as_seller")

    __table_args__ = (
        Index("idx_trade_listing", "listing_id"),
        Index("idx_trade_buyer", "buyer_id"),
        Index("idx_trade_seller", "seller_id"),
        Index("idx_trade_executed", "executed_at"),
        Index("idx_trade_settlement", "settlement_tx_hash"),
        CheckConstraint("amount > 0", name="positive_trade_amount"),
        CheckConstraint("price > 0", name="positive_trade_price"),
    )


class MarketPrice(Base):
    """
    Historial de precios del mercado.
    Datos OHLCV (Open, High, Low, Close, Volume) por intervalo.
    """
    __tablename__ = "marketplace_prices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_listings.id", ondelete="CASCADE"),
        nullable=False
    )

    # Intervalo de tiempo
    interval = Column(String(10), nullable=False)  # 1m, 5m, 15m, 1h, 4h, 1d
    timestamp = Column(DateTime(timezone=True), nullable=False)  # Inicio del intervalo

    # OHLCV
    open_price = Column(Numeric(18, 8), nullable=False)
    high_price = Column(Numeric(18, 8), nullable=False)
    low_price = Column(Numeric(18, 8), nullable=False)
    close_price = Column(Numeric(18, 8), nullable=False)
    volume = Column(Numeric(28, 8), default=0)  # Volumen en tokens
    volume_quote = Column(Numeric(28, 8), default=0)  # Volumen en moneda de cotización
    trades_count = Column(Integer, default=0)

    # VWAP (Volume Weighted Average Price)
    vwap = Column(Numeric(18, 8), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    listing = relationship("TokenListing", back_populates="price_history")

    __table_args__ = (
        Index("idx_price_listing_interval", "listing_id", "interval", "timestamp"),
        Index("idx_price_timestamp", "timestamp"),
        # Unique constraint para evitar duplicados
        Index(
            "uq_price_listing_interval_timestamp",
            "listing_id", "interval", "timestamp",
            unique=True
        ),
    )

    @property
    def price_change(self) -> float:
        """Cambio de precio (close - open)."""
        return float(self.close_price - self.open_price)

    @property
    def price_change_percent(self) -> float:
        """Cambio de precio en porcentaje."""
        if self.open_price == 0:
            return 0
        return float((self.close_price - self.open_price) / self.open_price * 100)


class UserTradingStats(Base):
    """
    Estadísticas de trading por usuario.
    Cache de métricas para dashboard.
    """
    __tablename__ = "user_trading_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    # Estadísticas totales
    total_trades = Column(Integer, default=0)
    total_buy_volume = Column(Numeric(28, 8), default=0)
    total_sell_volume = Column(Numeric(28, 8), default=0)
    total_fees_paid = Column(Numeric(18, 8), default=0)

    # Estadísticas de órdenes
    total_orders_placed = Column(Integer, default=0)
    total_orders_filled = Column(Integer, default=0)
    total_orders_cancelled = Column(Integer, default=0)

    # P&L
    realized_pnl = Column(Numeric(18, 8), default=0)

    # Timestamps
    first_trade_at = Column(DateTime(timezone=True), nullable=True)
    last_trade_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    user = relationship("User", backref="trading_stats")

    __table_args__ = (
        Index("idx_trading_stats_user", "user_id"),
    )
