"""
Endpoints del Marketplace Secundario.
Trading de tokens de inversión.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.marketplace import (
    TokenListing, TokenOrder, TokenTrade, OrderStatus, ListingStatus
)
from app.models.blockchain import ProjectToken, TokenHolding, UserWallet
from app.services.marketplace_service import MarketplaceService
from app.schemas.marketplace import (
    TokenListingCreate, TokenListingResponse, MarketTokenInfo,
    OrderCreate, OrderResponse, OrderBook, OrderCancelResponse, OrderExecutionResult,
    TradeResponse, TradeHistoryResponse, RecentTrade,
    TickerResponse, AllTickersResponse, MarketDataResponse, OHLCVData,
    UserTradingStatsResponse, UserMarketplacePortfolio, UserPortfolioItem,
    MarketplaceSummary
)

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


# ==================== LISTINGS ====================

@router.get("/tokens", response_model=List[MarketTokenInfo])
async def get_market_tokens(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtener todos los tokens listados en el marketplace.
    Incluye precio actual, volumen 24h, y cambio de precio.
    """
    service = MarketplaceService(db)
    return service.get_market_tokens(limit=limit)


@router.get("/tokens/{listing_id}", response_model=MarketTokenInfo)
async def get_token_info(
    listing_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener información detallada de un token listado."""
    service = MarketplaceService(db)
    tokens = service.get_market_tokens(limit=100)

    for token in tokens:
        if token.listing_id == listing_id:
            return token

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Token no encontrado en el marketplace"
    )


@router.get("/tokens/{listing_id}/ticker", response_model=TickerResponse)
async def get_token_ticker(
    listing_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener ticker de un token (precio actual, cambio 24h, volumen)."""
    service = MarketplaceService(db)
    ticker = service.get_ticker(listing_id)

    if not ticker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token no encontrado"
        )

    return ticker


@router.get("/tickers", response_model=AllTickersResponse)
async def get_all_tickers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener tickers de todos los tokens activos."""
    service = MarketplaceService(db)
    listings = service.get_active_listings(limit=100)

    tickers = []
    for listing in listings:
        ticker = service.get_ticker(listing.id)
        if ticker:
            tickers.append(ticker)

    return AllTickersResponse(
        tickers=tickers,
        last_updated=datetime.utcnow()
    )


# ==================== ORDERBOOK ====================

@router.get("/tokens/{listing_id}/orderbook", response_model=OrderBook)
async def get_orderbook(
    listing_id: UUID,
    depth: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtener el orderbook de un token.
    Muestra órdenes de compra (bids) y venta (asks) agregadas por precio.
    """
    service = MarketplaceService(db)

    try:
        return service.get_orderbook(listing_id, depth=depth)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/tokens/{listing_id}/trades", response_model=List[RecentTrade])
async def get_recent_trades(
    listing_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener trades recientes de un token."""
    service = MarketplaceService(db)
    trades = service.get_recent_trades(listing_id, limit=limit)

    return [
        RecentTrade(
            id=t.id,
            price=t.price,
            amount=t.amount,
            side="buy" if t.taker_order and t.taker_order.side.value == "buy" else "sell",
            executed_at=t.executed_at
        )
        for t in trades
    ]


@router.get("/tokens/{listing_id}/ohlcv", response_model=MarketDataResponse)
async def get_ohlcv_data(
    listing_id: UUID,
    interval: str = Query(default="1h", regex="^(1m|5m|15m|1h|4h|1d)$"),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtener datos OHLCV para gráficos de velas.

    Intervalos soportados: 1m, 5m, 15m, 1h, 4h, 1d
    """
    service = MarketplaceService(db)
    listing = service.get_listing(listing_id)

    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing no encontrado"
        )

    data = service.get_ohlcv(listing_id, interval=interval, limit=limit)

    return MarketDataResponse(
        listing_id=listing_id,
        token_symbol=listing.project_token.token_symbol if listing.project_token else "",
        interval=interval,
        data=data
    )


# ==================== ORDERS ====================

@router.post("/orders", response_model=OrderExecutionResult, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crear una orden de compra o venta.

    - **side**: "buy" o "sell"
    - **order_type**: "limit" (con precio) o "market" (precio de mercado)
    - **amount**: Cantidad de tokens
    - **price**: Precio por token (requerido para limit orders)

    La orden se ejecutará inmediatamente si hay match en el orderbook.
    """
    service = MarketplaceService(db)
    ip_address = request.client.host if request.client else None

    try:
        order, trades = service.create_order(
            user_id=current_user.id,
            order_data=order_data,
            ip_address=ip_address
        )

        # Construir respuesta
        order_response = OrderResponse(
            id=order.id,
            listing_id=order.listing_id,
            user_id=order.user_id,
            wallet_id=order.wallet_id,
            side=order.side.value,
            order_type=order.order_type.value,
            amount=order.amount,
            filled_amount=order.filled_amount,
            remaining_amount=order.remaining_amount,
            price=order.price,
            average_fill_price=order.average_fill_price,
            status=order.status.value,
            estimated_fee=order.estimated_fee,
            actual_fee=order.actual_fee,
            fill_percentage=order.fill_percentage,
            total_value=order.total_value,
            expires_at=order.expires_at,
            client_order_id=order.client_order_id,
            created_at=order.created_at,
            updated_at=order.updated_at,
            filled_at=order.filled_at,
            cancelled_at=order.cancelled_at
        )

        trade_responses = [
            TradeResponse(
                id=t.id,
                listing_id=t.listing_id,
                token_symbol=t.listing.project_token.token_symbol if t.listing and t.listing.project_token else "",
                buyer_id=t.buyer_id,
                seller_id=t.seller_id,
                amount=t.amount,
                price=t.price,
                total_value=t.total_value,
                maker_fee=t.maker_fee,
                taker_fee=t.taker_fee,
                total_fee=t.total_fee,
                is_settled_onchain=t.is_settled_onchain,
                settlement_tx_hash=t.settlement_tx_hash,
                executed_at=t.executed_at
            )
            for t in trades
        ]

        message = "Orden creada"
        if order.status.value == "filled":
            message = f"Orden ejecutada completamente. {len(trades)} trade(s)"
        elif order.status.value == "partially_filled":
            message = f"Orden parcialmente ejecutada. {len(trades)} trade(s)"

        return OrderExecutionResult(
            order=order_response,
            trades=trade_responses,
            message=message
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/orders", response_model=List[OrderResponse])
async def get_my_orders(
    status: Optional[str] = Query(default=None, regex="^(open|partially_filled|filled|cancelled|expired)$"),
    listing_id: Optional[UUID] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener mis órdenes."""
    service = MarketplaceService(db)

    order_status = None
    if status:
        order_status = OrderStatus(status)

    orders = service.get_user_orders(
        user_id=current_user.id,
        status=order_status,
        listing_id=listing_id,
        limit=limit,
        offset=offset
    )

    return [
        OrderResponse(
            id=o.id,
            listing_id=o.listing_id,
            user_id=o.user_id,
            wallet_id=o.wallet_id,
            side=o.side.value,
            order_type=o.order_type.value,
            amount=o.amount,
            filled_amount=o.filled_amount,
            remaining_amount=o.remaining_amount,
            price=o.price,
            average_fill_price=o.average_fill_price,
            status=o.status.value,
            estimated_fee=o.estimated_fee,
            actual_fee=o.actual_fee,
            fill_percentage=o.fill_percentage,
            total_value=o.total_value,
            expires_at=o.expires_at,
            client_order_id=o.client_order_id,
            created_at=o.created_at,
            updated_at=o.updated_at,
            filled_at=o.filled_at,
            cancelled_at=o.cancelled_at
        )
        for o in orders
    ]


@router.get("/orders/open", response_model=List[OrderResponse])
async def get_open_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener órdenes abiertas (pendientes de ejecución)."""
    service = MarketplaceService(db)
    orders = service.get_open_orders(current_user.id)

    return [
        OrderResponse(
            id=o.id,
            listing_id=o.listing_id,
            user_id=o.user_id,
            wallet_id=o.wallet_id,
            side=o.side.value,
            order_type=o.order_type.value,
            amount=o.amount,
            filled_amount=o.filled_amount,
            remaining_amount=o.remaining_amount,
            price=o.price,
            average_fill_price=o.average_fill_price,
            status=o.status.value,
            estimated_fee=o.estimated_fee,
            actual_fee=o.actual_fee,
            fill_percentage=o.fill_percentage,
            total_value=o.total_value,
            expires_at=o.expires_at,
            client_order_id=o.client_order_id,
            created_at=o.created_at,
            updated_at=o.updated_at,
            filled_at=o.filled_at,
            cancelled_at=o.cancelled_at
        )
        for o in orders
    ]


@router.delete("/orders/{order_id}", response_model=OrderCancelResponse)
async def cancel_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancelar una orden abierta."""
    service = MarketplaceService(db)

    try:
        order = service.cancel_order(current_user.id, order_id)
        return OrderCancelResponse(
            success=True,
            order_id=order.id,
            status=order.status.value,
            message="Orden cancelada exitosamente"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ==================== TRADES ====================

@router.get("/trades", response_model=TradeHistoryResponse)
async def get_my_trades(
    listing_id: Optional[UUID] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener mi historial de trades."""
    service = MarketplaceService(db)
    trades = service.get_user_trades(
        user_id=current_user.id,
        listing_id=listing_id,
        limit=limit,
        offset=offset
    )

    trade_responses = [
        TradeResponse(
            id=t.id,
            listing_id=t.listing_id,
            token_symbol=t.listing.project_token.token_symbol if t.listing and t.listing.project_token else "",
            buyer_id=t.buyer_id,
            seller_id=t.seller_id,
            amount=t.amount,
            price=t.price,
            total_value=t.total_value,
            maker_fee=t.maker_fee,
            taker_fee=t.taker_fee,
            total_fee=t.total_fee,
            is_settled_onchain=t.is_settled_onchain,
            settlement_tx_hash=t.settlement_tx_hash,
            executed_at=t.executed_at
        )
        for t in trades
    ]

    # Contar total (simplificado)
    total = len(trades) + offset

    return TradeHistoryResponse(
        trades=trade_responses,
        total=total,
        page=offset // limit + 1 if limit > 0 else 1,
        page_size=limit
    )


# ==================== PORTFOLIO ====================

@router.get("/portfolio", response_model=UserMarketplacePortfolio)
async def get_marketplace_portfolio(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtener portfolio del usuario para el marketplace.
    Muestra tokens que posee y si son tradeable.
    """
    # Obtener holdings del usuario
    holdings = db.query(TokenHolding).join(UserWallet).filter(
        UserWallet.user_id == current_user.id,
        TokenHolding.balance > 0
    ).all()

    items = []
    total_value = Decimal("0")
    total_pnl = Decimal("0")

    for holding in holdings:
        token = holding.project_token
        if not token:
            continue

        # Verificar si está listado
        listing = db.query(TokenListing).filter(
            TokenListing.project_token_id == token.id,
            TokenListing.status == ListingStatus.ACTIVE
        ).first()

        current_price = token.price_per_token
        current_value = holding.balance * current_price
        avg_cost = holding.average_cost_basis or current_price
        unrealized_pnl = (current_price - avg_cost) * holding.balance
        unrealized_pnl_percent = Decimal("0")
        if avg_cost > 0:
            unrealized_pnl_percent = ((current_price - avg_cost) / avg_cost) * 100

        total_value += current_value
        total_pnl += unrealized_pnl

        items.append(UserPortfolioItem(
            token_id=token.id,
            listing_id=listing.id if listing else None,
            token_symbol=token.token_symbol,
            token_name=token.token_name,
            balance=holding.balance,
            available_balance=holding.balance - holding.locked_balance,
            locked_balance=holding.locked_balance,
            average_cost=avg_cost,
            current_price=current_price,
            current_value=current_value,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_percent=unrealized_pnl_percent,
            is_tradeable=listing is not None
        ))

    return UserMarketplacePortfolio(
        total_value=total_value,
        total_unrealized_pnl=total_pnl,
        items=items
    )


@router.get("/stats", response_model=UserTradingStatsResponse)
async def get_trading_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener estadísticas de trading del usuario."""
    from app.models.marketplace import UserTradingStats

    stats = db.query(UserTradingStats).filter(
        UserTradingStats.user_id == current_user.id
    ).first()

    if not stats:
        # Retornar stats vacías
        return UserTradingStatsResponse(
            user_id=current_user.id,
            total_trades=0,
            total_buy_volume=Decimal("0"),
            total_sell_volume=Decimal("0"),
            total_fees_paid=Decimal("0"),
            total_orders_placed=0,
            total_orders_filled=0,
            total_orders_cancelled=0,
            realized_pnl=Decimal("0"),
            first_trade_at=None,
            last_trade_at=None
        )

    return UserTradingStatsResponse(
        user_id=stats.user_id,
        total_trades=stats.total_trades,
        total_buy_volume=stats.total_buy_volume,
        total_sell_volume=stats.total_sell_volume,
        total_fees_paid=stats.total_fees_paid,
        total_orders_placed=stats.total_orders_placed,
        total_orders_filled=stats.total_orders_filled,
        total_orders_cancelled=stats.total_orders_cancelled,
        realized_pnl=stats.realized_pnl,
        first_trade_at=stats.first_trade_at,
        last_trade_at=stats.last_trade_at
    )


# ==================== MARKETPLACE SUMMARY ====================

@router.get("/summary", response_model=MarketplaceSummary)
async def get_marketplace_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener resumen del marketplace."""
    from sqlalchemy import func
    from datetime import timedelta

    now = datetime.utcnow()
    time_24h_ago = now - timedelta(hours=24)

    # Contar listings
    total_listings = db.query(func.count(TokenListing.id)).scalar() or 0
    active_listings = db.query(func.count(TokenListing.id)).filter(
        TokenListing.status == ListingStatus.ACTIVE
    ).scalar() or 0

    # Volumen y trades 24h
    stats_24h = db.query(
        func.sum(TokenTrade.amount).label('volume'),
        func.count(TokenTrade.id).label('trades')
    ).filter(
        TokenTrade.executed_at >= time_24h_ago
    ).first()

    # Volumen y trades totales
    stats_all = db.query(
        func.sum(TokenListing.total_volume).label('volume'),
        func.sum(TokenListing.total_trades).label('trades')
    ).scalar()

    # Obtener top tokens
    service = MarketplaceService(db)
    all_tokens = service.get_market_tokens(limit=50)

    # Top gainers (mayor cambio positivo)
    top_gainers = sorted(
        [t for t in all_tokens if t.price_change_percent_24h and t.price_change_percent_24h > 0],
        key=lambda x: x.price_change_percent_24h or 0,
        reverse=True
    )[:5]

    # Top losers (mayor cambio negativo)
    top_losers = sorted(
        [t for t in all_tokens if t.price_change_percent_24h and t.price_change_percent_24h < 0],
        key=lambda x: x.price_change_percent_24h or 0
    )[:5]

    # Most traded (mayor volumen)
    most_traded = sorted(
        all_tokens,
        key=lambda x: x.volume_24h or 0,
        reverse=True
    )[:5]

    # Recently listed
    recently_listed = all_tokens[:5]  # Ya vienen ordenados

    return MarketplaceSummary(
        total_listings=total_listings,
        active_listings=active_listings,
        total_volume_24h=stats_24h.volume or Decimal("0") if stats_24h else Decimal("0"),
        total_trades_24h=stats_24h.trades or 0 if stats_24h else 0,
        total_volume_all_time=stats_all or Decimal("0"),
        total_trades_all_time=0,  # Simplificado
        top_gainers=top_gainers,
        top_losers=top_losers,
        most_traded=most_traded,
        recently_listed=recently_listed
    )
