"""
Servicio de Marketplace Secundario para FinCore.
Incluye order matching engine y gestión de trades.
"""
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, desc, asc, func
from sqlalchemy.orm import Session

from app.models.marketplace import (
    TokenListing, TokenOrder, TokenTrade, MarketPrice, UserTradingStats,
    OrderSide, OrderType, OrderStatus, ListingStatus
)
from app.models.blockchain import ProjectToken, TokenHolding, UserWallet
from app.models.audit import AuditLog, AuditAction
from app.schemas.marketplace import (
    OrderCreate, OrderBook, OrderBookEntry, MarketTokenInfo,
    TickerResponse, OHLCVData
)

logger = logging.getLogger(__name__)


class MarketplaceService:
    """Servicio principal del marketplace."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== LISTINGS ====================

    def get_listing(self, listing_id: UUID) -> Optional[TokenListing]:
        """Obtener listing por ID."""
        return self.db.query(TokenListing).filter(
            TokenListing.id == listing_id
        ).first()

    def get_listing_by_token(self, project_token_id: UUID) -> Optional[TokenListing]:
        """Obtener listing por token ID."""
        return self.db.query(TokenListing).filter(
            TokenListing.project_token_id == project_token_id
        ).first()

    def get_active_listings(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[TokenListing]:
        """Obtener listings activos."""
        return self.db.query(TokenListing).filter(
            TokenListing.status == ListingStatus.ACTIVE
        ).order_by(desc(TokenListing.total_volume)).offset(offset).limit(limit).all()

    def create_listing(
        self,
        project_token_id: UUID,
        min_order_amount: Decimal = Decimal("1"),
        max_order_amount: Optional[Decimal] = None,
        maker_fee_percent: Decimal = Decimal("0.001"),
        taker_fee_percent: Decimal = Decimal("0.002"),
        daily_volume_limit: Optional[Decimal] = None,
    ) -> TokenListing:
        """Crear nuevo listing."""
        # Verificar que el token existe y está activo
        token = self.db.query(ProjectToken).filter(
            ProjectToken.id == project_token_id,
            ProjectToken.is_active == True
        ).first()

        if not token:
            raise ValueError("Token no encontrado o no está activo")

        # Verificar que no existe listing
        existing = self.get_listing_by_token(project_token_id)
        if existing:
            raise ValueError("Ya existe un listing para este token")

        listing = TokenListing(
            project_token_id=project_token_id,
            status=ListingStatus.ACTIVE,
            min_order_amount=min_order_amount,
            max_order_amount=max_order_amount,
            maker_fee_percent=maker_fee_percent,
            taker_fee_percent=taker_fee_percent,
            daily_volume_limit=daily_volume_limit,
            listed_at=datetime.utcnow(),
        )

        self.db.add(listing)
        self.db.commit()
        self.db.refresh(listing)

        logger.info(f"Listing creado para token {token.token_symbol}: {listing.id}")
        return listing

    def get_market_tokens(self, limit: int = 50) -> List[MarketTokenInfo]:
        """Obtener información de mercado de tokens listados."""
        listings = self.get_active_listings(limit=limit)
        result = []

        for listing in listings:
            token = listing.project_token
            if not token:
                continue

            # Obtener precio actual (último trade o precio base del token)
            last_trade = self.db.query(TokenTrade).filter(
                TokenTrade.listing_id == listing.id
            ).order_by(desc(TokenTrade.executed_at)).first()

            current_price = last_trade.price if last_trade else token.price_per_token

            # Calcular cambio 24h
            price_24h_ago = self._get_price_at_time(
                listing.id,
                datetime.utcnow() - timedelta(hours=24)
            )
            price_change_24h = None
            price_change_percent_24h = None
            if price_24h_ago and price_24h_ago > 0:
                price_change_24h = current_price - price_24h_ago
                price_change_percent_24h = (price_change_24h / price_24h_ago) * 100

            # Volumen 24h
            volume_24h = self._get_volume_since(
                listing.id,
                datetime.utcnow() - timedelta(hours=24)
            )

            # Best bid/ask
            best_bid, best_ask = self._get_best_bid_ask(listing.id)
            spread = None
            if best_bid and best_ask:
                spread = best_ask - best_bid

            result.append(MarketTokenInfo(
                listing_id=listing.id,
                token_id=token.id,
                token_symbol=token.token_symbol,
                token_name=token.token_name,
                project_id=token.project_id,
                project_name=token.project.nombre if token.project else "",
                current_price=current_price,
                price_change_24h=price_change_24h,
                price_change_percent_24h=price_change_percent_24h,
                volume_24h=volume_24h,
                market_cap=current_price * token.tokens_sold,
                circulating_supply=token.tokens_sold,
                total_supply=token.total_supply,
                total_trades=listing.total_trades,
                status=listing.status.value,
                best_bid=best_bid,
                best_ask=best_ask,
                spread=spread,
            ))

        return result

    # ==================== ORDERS ====================

    def create_order(
        self,
        user_id: UUID,
        order_data: OrderCreate,
        ip_address: Optional[str] = None
    ) -> Tuple[TokenOrder, List[TokenTrade]]:
        """
        Crear orden y ejecutar matching.
        Retorna la orden y lista de trades ejecutados.
        """
        # Validaciones
        listing = self.get_listing(order_data.listing_id)
        if not listing or listing.status != ListingStatus.ACTIVE:
            raise ValueError("Listing no encontrado o no está activo")

        # Validar monto
        if order_data.amount < listing.min_order_amount:
            raise ValueError(f"Monto mínimo: {listing.min_order_amount}")
        if listing.max_order_amount and order_data.amount > listing.max_order_amount:
            raise ValueError(f"Monto máximo: {listing.max_order_amount}")

        # Para órdenes de venta, verificar balance
        if order_data.side == OrderSide.SELL:
            available = self._get_available_balance(
                user_id, listing.project_token_id
            )
            if available < order_data.amount:
                raise ValueError(f"Balance insuficiente. Disponible: {available}")

        # Calcular fee estimado
        fee_percent = (
            listing.taker_fee_percent
            if order_data.order_type == OrderType.MARKET
            else listing.maker_fee_percent
        )
        estimated_fee = order_data.amount * (order_data.price or Decimal("0")) * fee_percent

        # Crear orden
        order = TokenOrder(
            listing_id=listing.id,
            user_id=user_id,
            wallet_id=order_data.wallet_id,
            side=OrderSide(order_data.side.value),
            order_type=OrderType(order_data.order_type.value),
            amount=order_data.amount,
            remaining_amount=order_data.amount,
            filled_amount=Decimal("0"),
            price=order_data.price,
            status=OrderStatus.OPEN,
            estimated_fee=estimated_fee,
            expires_at=order_data.expires_at,
            client_order_id=order_data.client_order_id,
            ip_address=ip_address,
        )

        self.db.add(order)
        self.db.flush()  # Obtener ID sin commit

        # Bloquear tokens para venta
        if order.side == OrderSide.SELL:
            self._lock_tokens(user_id, listing.project_token_id, order.amount)

        # Ejecutar matching
        trades = self._match_order(order, listing)

        # Actualizar estado de la orden
        if order.remaining_amount == 0:
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.utcnow()
        elif order.filled_amount > 0:
            order.status = OrderStatus.PARTIALLY_FILLED

        self.db.commit()
        self.db.refresh(order)

        # Log de auditoría
        self._log_order_created(user_id, order)

        return order, trades

    def cancel_order(self, user_id: UUID, order_id: UUID) -> TokenOrder:
        """Cancelar orden abierta."""
        order = self.db.query(TokenOrder).filter(
            TokenOrder.id == order_id,
            TokenOrder.user_id == user_id,
            TokenOrder.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED])
        ).first()

        if not order:
            raise ValueError("Orden no encontrada o no puede ser cancelada")

        # Desbloquear tokens restantes si es venta
        if order.side == OrderSide.SELL and order.remaining_amount > 0:
            listing = self.get_listing(order.listing_id)
            if listing:
                self._unlock_tokens(
                    user_id,
                    listing.project_token_id,
                    order.remaining_amount
                )

        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.utcnow()
        order.cancellation_reason = "Cancelled by user"

        self.db.commit()
        self.db.refresh(order)

        logger.info(f"Orden cancelada: {order_id}")
        return order

    def get_user_orders(
        self,
        user_id: UUID,
        status: Optional[OrderStatus] = None,
        listing_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[TokenOrder]:
        """Obtener órdenes del usuario."""
        query = self.db.query(TokenOrder).filter(TokenOrder.user_id == user_id)

        if status:
            query = query.filter(TokenOrder.status == status)
        if listing_id:
            query = query.filter(TokenOrder.listing_id == listing_id)

        return query.order_by(desc(TokenOrder.created_at)).offset(offset).limit(limit).all()

    def get_open_orders(self, user_id: UUID) -> List[TokenOrder]:
        """Obtener órdenes abiertas del usuario."""
        return self.get_user_orders(
            user_id,
            status=OrderStatus.OPEN
        ) + self.get_user_orders(
            user_id,
            status=OrderStatus.PARTIALLY_FILLED
        )

    # ==================== ORDER MATCHING ====================

    def _match_order(
        self,
        taker_order: TokenOrder,
        listing: TokenListing
    ) -> List[TokenTrade]:
        """
        Motor de matching de órdenes.
        Implementa Price-Time Priority (FIFO).
        """
        trades = []

        # Obtener órdenes contrarias ordenadas por precio y tiempo
        opposite_side = OrderSide.SELL if taker_order.side == OrderSide.BUY else OrderSide.BUY

        query = self.db.query(TokenOrder).filter(
            TokenOrder.listing_id == listing.id,
            TokenOrder.side == opposite_side,
            TokenOrder.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            TokenOrder.user_id != taker_order.user_id,  # No self-trade
        )

        # Ordenar por precio (mejor precio primero) y tiempo (FIFO)
        if taker_order.side == OrderSide.BUY:
            # Comprando: queremos los asks más bajos primero
            query = query.order_by(asc(TokenOrder.price), asc(TokenOrder.created_at))
        else:
            # Vendiendo: queremos los bids más altos primero
            query = query.order_by(desc(TokenOrder.price), asc(TokenOrder.created_at))

        maker_orders = query.all()

        for maker_order in maker_orders:
            if taker_order.remaining_amount <= 0:
                break

            # Verificar precio match
            if taker_order.order_type == OrderType.LIMIT:
                if taker_order.side == OrderSide.BUY:
                    # Buy order: maker price debe ser <= taker price
                    if maker_order.price > taker_order.price:
                        break  # No más matches posibles (ordenado por precio)
                else:
                    # Sell order: maker price debe ser >= taker price
                    if maker_order.price < taker_order.price:
                        break

            # Calcular cantidad a ejecutar
            match_amount = min(taker_order.remaining_amount, maker_order.remaining_amount)
            match_price = maker_order.price  # Precio del maker (price improvement para taker)

            # Crear trade
            trade = self._execute_trade(
                listing, maker_order, taker_order, match_amount, match_price
            )
            trades.append(trade)

            # Actualizar órdenes
            maker_order.filled_amount += match_amount
            maker_order.remaining_amount -= match_amount
            taker_order.filled_amount += match_amount
            taker_order.remaining_amount -= match_amount

            # Actualizar precio promedio
            self._update_average_fill_price(maker_order, match_amount, match_price)
            self._update_average_fill_price(taker_order, match_amount, match_price)

            # Actualizar estado del maker
            if maker_order.remaining_amount == 0:
                maker_order.status = OrderStatus.FILLED
                maker_order.filled_at = datetime.utcnow()
            else:
                maker_order.status = OrderStatus.PARTIALLY_FILLED

        return trades

    def _execute_trade(
        self,
        listing: TokenListing,
        maker_order: TokenOrder,
        taker_order: TokenOrder,
        amount: Decimal,
        price: Decimal
    ) -> TokenTrade:
        """Ejecutar un trade entre dos órdenes."""
        total_value = amount * price

        # Calcular fees
        maker_fee = total_value * listing.maker_fee_percent
        taker_fee = total_value * listing.taker_fee_percent
        total_fee = maker_fee + taker_fee

        # Determinar buyer/seller
        if taker_order.side == OrderSide.BUY:
            buyer_id = taker_order.user_id
            seller_id = maker_order.user_id
        else:
            buyer_id = maker_order.user_id
            seller_id = taker_order.user_id

        trade = TokenTrade(
            listing_id=listing.id,
            maker_order_id=maker_order.id,
            taker_order_id=taker_order.id,
            buyer_id=buyer_id,
            seller_id=seller_id,
            amount=amount,
            price=price,
            total_value=total_value,
            maker_fee=maker_fee,
            taker_fee=taker_fee,
            total_fee=total_fee,
        )

        self.db.add(trade)

        # Actualizar fees en órdenes
        maker_order.actual_fee += maker_fee
        taker_order.actual_fee += taker_fee

        # Actualizar estadísticas del listing
        listing.total_volume += amount
        listing.total_trades += 1
        listing.total_fees_collected += total_fee
        listing.current_daily_volume += amount

        # Transferir tokens
        self._transfer_tokens(
            listing.project_token_id,
            seller_id,
            buyer_id,
            amount,
            price
        )

        # Actualizar precio de mercado
        self._update_market_price(listing.id, price, amount)

        # Actualizar stats de usuarios
        self._update_trading_stats(buyer_id, amount, total_value, taker_fee, is_buy=True)
        self._update_trading_stats(seller_id, amount, total_value, maker_fee, is_buy=False)

        logger.info(
            f"Trade ejecutado: {amount} tokens @ {price} "
            f"(buyer: {buyer_id}, seller: {seller_id})"
        )

        return trade

    # ==================== ORDERBOOK ====================

    def get_orderbook(
        self,
        listing_id: UUID,
        depth: int = 20
    ) -> OrderBook:
        """Obtener orderbook agregado."""
        listing = self.get_listing(listing_id)
        if not listing:
            raise ValueError("Listing no encontrado")

        # Agregar bids (órdenes de compra)
        bids_raw = self.db.query(
            TokenOrder.price,
            func.sum(TokenOrder.remaining_amount).label('amount'),
            func.count(TokenOrder.id).label('orders_count')
        ).filter(
            TokenOrder.listing_id == listing_id,
            TokenOrder.side == OrderSide.BUY,
            TokenOrder.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            TokenOrder.price.isnot(None)
        ).group_by(TokenOrder.price).order_by(desc(TokenOrder.price)).limit(depth).all()

        bids = [
            OrderBookEntry(
                price=b.price,
                amount=b.amount,
                total=b.price * b.amount,
                orders_count=b.orders_count
            )
            for b in bids_raw
        ]

        # Agregar asks (órdenes de venta)
        asks_raw = self.db.query(
            TokenOrder.price,
            func.sum(TokenOrder.remaining_amount).label('amount'),
            func.count(TokenOrder.id).label('orders_count')
        ).filter(
            TokenOrder.listing_id == listing_id,
            TokenOrder.side == OrderSide.SELL,
            TokenOrder.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            TokenOrder.price.isnot(None)
        ).group_by(TokenOrder.price).order_by(asc(TokenOrder.price)).limit(depth).all()

        asks = [
            OrderBookEntry(
                price=a.price,
                amount=a.amount,
                total=a.price * a.amount,
                orders_count=a.orders_count
            )
            for a in asks_raw
        ]

        # Calcular spread
        spread = None
        spread_percent = None
        if bids and asks:
            best_bid = bids[0].price
            best_ask = asks[0].price
            spread = best_ask - best_bid
            if best_bid > 0:
                spread_percent = (spread / best_bid) * 100

        return OrderBook(
            listing_id=listing_id,
            token_symbol=listing.project_token.token_symbol if listing.project_token else "",
            bids=bids,
            asks=asks,
            spread=spread,
            spread_percent=spread_percent,
            last_updated=datetime.utcnow()
        )

    # ==================== TRADES ====================

    def get_user_trades(
        self,
        user_id: UUID,
        listing_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[TokenTrade]:
        """Obtener trades del usuario."""
        query = self.db.query(TokenTrade).filter(
            or_(
                TokenTrade.buyer_id == user_id,
                TokenTrade.seller_id == user_id
            )
        )

        if listing_id:
            query = query.filter(TokenTrade.listing_id == listing_id)

        return query.order_by(desc(TokenTrade.executed_at)).offset(offset).limit(limit).all()

    def get_recent_trades(
        self,
        listing_id: UUID,
        limit: int = 50
    ) -> List[TokenTrade]:
        """Obtener trades recientes de un listing."""
        return self.db.query(TokenTrade).filter(
            TokenTrade.listing_id == listing_id
        ).order_by(desc(TokenTrade.executed_at)).limit(limit).all()

    # ==================== MARKET DATA ====================

    def get_ticker(self, listing_id: UUID) -> Optional[TickerResponse]:
        """Obtener ticker de un token."""
        listing = self.get_listing(listing_id)
        if not listing or not listing.project_token:
            return None

        token = listing.project_token
        now = datetime.utcnow()
        time_24h_ago = now - timedelta(hours=24)

        # Último trade
        last_trade = self.db.query(TokenTrade).filter(
            TokenTrade.listing_id == listing_id
        ).order_by(desc(TokenTrade.executed_at)).first()

        last_price = last_trade.price if last_trade else token.price_per_token

        # Estadísticas 24h
        stats_24h = self.db.query(
            func.min(TokenTrade.price).label('low'),
            func.max(TokenTrade.price).label('high'),
            func.sum(TokenTrade.amount).label('volume'),
            func.sum(TokenTrade.total_value).label('volume_quote'),
            func.count(TokenTrade.id).label('trades_count')
        ).filter(
            TokenTrade.listing_id == listing_id,
            TokenTrade.executed_at >= time_24h_ago
        ).first()

        # Precio hace 24h
        price_24h_ago = self._get_price_at_time(listing_id, time_24h_ago)
        price_change = last_price - (price_24h_ago or last_price)
        price_change_percent = Decimal("0")
        if price_24h_ago and price_24h_ago > 0:
            price_change_percent = (price_change / price_24h_ago) * 100

        # Best bid/ask
        best_bid, best_ask = self._get_best_bid_ask(listing_id)

        return TickerResponse(
            listing_id=listing_id,
            token_symbol=token.token_symbol,
            token_name=token.token_name,
            last_price=last_price,
            bid=best_bid,
            ask=best_ask,
            price_change_24h=price_change,
            price_change_percent_24h=price_change_percent,
            high_24h=stats_24h.high or last_price,
            low_24h=stats_24h.low or last_price,
            volume_24h=stats_24h.volume or Decimal("0"),
            volume_quote_24h=stats_24h.volume_quote or Decimal("0"),
            trades_24h=stats_24h.trades_count or 0,
            timestamp=now
        )

    def get_ohlcv(
        self,
        listing_id: UUID,
        interval: str = "1h",
        limit: int = 100
    ) -> List[OHLCVData]:
        """Obtener datos OHLCV para gráficos."""
        prices = self.db.query(MarketPrice).filter(
            MarketPrice.listing_id == listing_id,
            MarketPrice.interval == interval
        ).order_by(desc(MarketPrice.timestamp)).limit(limit).all()

        return [
            OHLCVData(
                timestamp=p.timestamp,
                open=p.open_price,
                high=p.high_price,
                low=p.low_price,
                close=p.close_price,
                volume=p.volume,
                trades_count=p.trades_count,
                vwap=p.vwap
            )
            for p in reversed(prices)  # Ordenar cronológicamente
        ]

    # ==================== HELPERS ====================

    def _get_available_balance(
        self,
        user_id: UUID,
        project_token_id: UUID
    ) -> Decimal:
        """Obtener balance disponible del usuario."""
        holding = self.db.query(TokenHolding).join(UserWallet).filter(
            UserWallet.user_id == user_id,
            TokenHolding.project_token_id == project_token_id
        ).first()

        if not holding:
            return Decimal("0")

        return holding.balance - holding.locked_balance

    def _lock_tokens(
        self,
        user_id: UUID,
        project_token_id: UUID,
        amount: Decimal
    ):
        """Bloquear tokens para orden de venta."""
        holding = self.db.query(TokenHolding).join(UserWallet).filter(
            UserWallet.user_id == user_id,
            TokenHolding.project_token_id == project_token_id
        ).first()

        if holding:
            holding.locked_balance += amount

    def _unlock_tokens(
        self,
        user_id: UUID,
        project_token_id: UUID,
        amount: Decimal
    ):
        """Desbloquear tokens."""
        holding = self.db.query(TokenHolding).join(UserWallet).filter(
            UserWallet.user_id == user_id,
            TokenHolding.project_token_id == project_token_id
        ).first()

        if holding:
            holding.locked_balance = max(Decimal("0"), holding.locked_balance - amount)

    def _transfer_tokens(
        self,
        project_token_id: UUID,
        seller_id: UUID,
        buyer_id: UUID,
        amount: Decimal,
        price: Decimal
    ):
        """Transferir tokens del vendedor al comprador."""
        # Obtener o crear holding del comprador
        buyer_wallet = self.db.query(UserWallet).filter(
            UserWallet.user_id == buyer_id,
            UserWallet.is_primary == True
        ).first()

        if not buyer_wallet:
            raise ValueError("Comprador no tiene wallet")

        buyer_holding = self.db.query(TokenHolding).filter(
            TokenHolding.wallet_id == buyer_wallet.id,
            TokenHolding.project_token_id == project_token_id
        ).first()

        if not buyer_holding:
            buyer_holding = TokenHolding(
                wallet_id=buyer_wallet.id,
                project_token_id=project_token_id,
                balance=Decimal("0"),
                first_purchase_at=datetime.utcnow()
            )
            self.db.add(buyer_holding)

        # Actualizar holding del vendedor
        seller_holding = self.db.query(TokenHolding).join(UserWallet).filter(
            UserWallet.user_id == seller_id,
            TokenHolding.project_token_id == project_token_id
        ).first()

        if seller_holding:
            seller_holding.balance -= amount
            seller_holding.locked_balance -= amount
            seller_holding.last_activity_at = datetime.utcnow()

        # Actualizar holding del comprador
        total_cost = amount * price

        # Recalcular average cost basis
        if buyer_holding.balance > 0 and buyer_holding.average_cost_basis:
            old_value = buyer_holding.balance * buyer_holding.average_cost_basis
            new_value = old_value + total_cost
            buyer_holding.average_cost_basis = new_value / (buyer_holding.balance + amount)
        else:
            buyer_holding.average_cost_basis = price

        buyer_holding.balance += amount
        buyer_holding.total_invested += total_cost
        buyer_holding.last_activity_at = datetime.utcnow()

    def _update_average_fill_price(
        self,
        order: TokenOrder,
        amount: Decimal,
        price: Decimal
    ):
        """Actualizar precio promedio de fill."""
        if order.average_fill_price is None:
            order.average_fill_price = price
        else:
            # Weighted average
            old_value = order.average_fill_price * (order.filled_amount - amount)
            new_value = price * amount
            order.average_fill_price = (old_value + new_value) / order.filled_amount

    def _update_market_price(
        self,
        listing_id: UUID,
        price: Decimal,
        volume: Decimal
    ):
        """Actualizar precio de mercado (candlestick data)."""
        now = datetime.utcnow()
        interval = "1h"

        # Truncar a la hora
        timestamp = now.replace(minute=0, second=0, microsecond=0)

        existing = self.db.query(MarketPrice).filter(
            MarketPrice.listing_id == listing_id,
            MarketPrice.interval == interval,
            MarketPrice.timestamp == timestamp
        ).first()

        if existing:
            existing.high_price = max(existing.high_price, price)
            existing.low_price = min(existing.low_price, price)
            existing.close_price = price
            existing.volume += volume
            existing.trades_count += 1
            # Recalcular VWAP
            existing.vwap = (
                (existing.vwap * (existing.volume - volume) + price * volume)
                / existing.volume
            ) if existing.volume > 0 else price
        else:
            market_price = MarketPrice(
                listing_id=listing_id,
                interval=interval,
                timestamp=timestamp,
                open_price=price,
                high_price=price,
                low_price=price,
                close_price=price,
                volume=volume,
                trades_count=1,
                vwap=price
            )
            self.db.add(market_price)

    def _update_trading_stats(
        self,
        user_id: UUID,
        amount: Decimal,
        value: Decimal,
        fee: Decimal,
        is_buy: bool
    ):
        """Actualizar estadísticas de trading del usuario."""
        stats = self.db.query(UserTradingStats).filter(
            UserTradingStats.user_id == user_id
        ).first()

        if not stats:
            stats = UserTradingStats(
                user_id=user_id,
                first_trade_at=datetime.utcnow()
            )
            self.db.add(stats)

        stats.total_trades += 1
        stats.total_fees_paid += fee
        stats.last_trade_at = datetime.utcnow()

        if is_buy:
            stats.total_buy_volume += amount
        else:
            stats.total_sell_volume += amount

    def _get_price_at_time(
        self,
        listing_id: UUID,
        timestamp: datetime
    ) -> Optional[Decimal]:
        """Obtener precio aproximado en un momento dado."""
        trade = self.db.query(TokenTrade).filter(
            TokenTrade.listing_id == listing_id,
            TokenTrade.executed_at <= timestamp
        ).order_by(desc(TokenTrade.executed_at)).first()

        return trade.price if trade else None

    def _get_volume_since(
        self,
        listing_id: UUID,
        since: datetime
    ) -> Decimal:
        """Obtener volumen desde un timestamp."""
        result = self.db.query(func.sum(TokenTrade.amount)).filter(
            TokenTrade.listing_id == listing_id,
            TokenTrade.executed_at >= since
        ).scalar()

        return result or Decimal("0")

    def _get_best_bid_ask(
        self,
        listing_id: UUID
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """Obtener mejor bid y ask."""
        best_bid = self.db.query(func.max(TokenOrder.price)).filter(
            TokenOrder.listing_id == listing_id,
            TokenOrder.side == OrderSide.BUY,
            TokenOrder.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED])
        ).scalar()

        best_ask = self.db.query(func.min(TokenOrder.price)).filter(
            TokenOrder.listing_id == listing_id,
            TokenOrder.side == OrderSide.SELL,
            TokenOrder.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED])
        ).scalar()

        return best_bid, best_ask

    def _log_order_created(self, user_id: UUID, order: TokenOrder):
        """Log de auditoría para orden creada."""
        self.db.add(AuditLog(
            user_id=user_id,
            action=AuditAction.CREATE.value if hasattr(AuditAction, 'CREATE') else "create",
            resource_type="marketplace_order",
            resource_id=str(order.id),
            description=f"Orden {order.side.value} creada: {order.amount} tokens @ {order.price}",
        ))
