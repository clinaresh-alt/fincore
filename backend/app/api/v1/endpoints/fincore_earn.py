"""
Endpoints para Fincore Earn - Productos de Rendimiento.
Sistema de ahorro e inversión con rendimientos.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID
from decimal import Decimal

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.fincore_earn import (
    EarnProduct, EarnPosition, EarnTransaction, YieldDistribution, EarnPromotion,
    EarnProductType, EarnProductStatus, EarnPositionStatus, EarnTransactionType,
    YieldDistributionStatus
)
from app.schemas.fincore_earn import (
    EarnProductResponse, EarnProductList,
    EarnPositionCreate, EarnPositionResponse, EarnPositionList,
    EarnPositionWithdraw, EarnPositionUpdate,
    EarnTransactionResponse, EarnTransactionList,
    YieldDistributionResponse, YieldDistributionList,
    EarnPromotionResponse, EarnPromotionApply, EarnPromotionValidation,
    EarnAnalytics, EarnSummary, EarnCalculatorRequest, EarnCalculatorResponse
)
from app.infrastructure import get_logger

router = APIRouter(prefix="/earn", tags=["Fincore Earn"])
logger = get_logger(__name__)


# =====================
# Products
# =====================

@router.get("/products", response_model=EarnProductList)
async def list_earn_products(
    product_type: Optional[EarnProductType] = None,
    currency: Optional[str] = None,
    include_closed: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar productos de rendimiento disponibles."""
    query = select(EarnProduct)

    if not include_closed:
        query = query.where(EarnProduct.status.in_([
            EarnProductStatus.ACTIVE,
            EarnProductStatus.COMING_SOON
        ]))

    if product_type:
        query = query.where(EarnProduct.product_type == product_type)

    if currency:
        query = query.where(EarnProduct.currency == currency)

    query = query.order_by(EarnProduct.display_order, EarnProduct.apy_base.desc())

    result = await db.execute(query)
    products = result.scalars().all()

    # Contar por tipo
    by_type = {}
    for p in products:
        type_key = p.product_type.value
        by_type[type_key] = by_type.get(type_key, 0) + 1

    return EarnProductList(
        products=[
            EarnProductResponse(
                **{k: v for k, v in p.__dict__.items() if not k.startswith("_")},
                current_apy=p.current_apy,
                available_capacity=p.available_capacity if p.total_capacity else None
            )
            for p in products
        ],
        total=len(products),
        by_type=by_type
    )


@router.get("/products/{product_id}", response_model=EarnProductResponse)
async def get_earn_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener detalle de producto de rendimiento."""
    query = select(EarnProduct).where(EarnProduct.id == product_id)

    result = await db.execute(query)
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado"
        )

    return EarnProductResponse(
        **{k: v for k, v in product.__dict__.items() if not k.startswith("_")},
        current_apy=product.current_apy,
        available_capacity=product.available_capacity if product.total_capacity else None
    )


# =====================
# Positions
# =====================

@router.post("/positions", response_model=EarnPositionResponse, status_code=status.HTTP_201_CREATED)
async def create_earn_position(
    position_data: EarnPositionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Crear posición en producto de rendimiento (depositar)."""
    # Obtener producto
    product_query = select(EarnProduct).where(
        EarnProduct.id == position_data.product_id,
        EarnProduct.status == EarnProductStatus.ACTIVE
    )
    result = await db.execute(product_query)
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no disponible"
        )

    # Validar monto
    if position_data.amount < product.min_deposit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Depósito mínimo: {product.min_deposit} {product.currency}"
        )

    if product.max_deposit and position_data.amount > product.max_deposit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Depósito máximo: {product.max_deposit} {product.currency}"
        )

    # Validar capacidad
    if product.total_capacity:
        available = product.available_capacity
        if position_data.amount > available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Capacidad disponible: {available} {product.currency}"
            )

    # Calcular fecha de madurez
    maturity_date = None
    if product.lock_period_days > 0:
        maturity_date = datetime.utcnow() + timedelta(days=product.lock_period_days)

    # Crear posición
    position = EarnPosition(
        position_number=EarnPosition.generate_position_number(),
        user_id=current_user.id,
        product_id=product.id,
        principal=position_data.amount,
        currency=product.currency,
        locked_apy=product.current_apy if product.lock_period_days > 0 else None,
        status=EarnPositionStatus.ACTIVE,
        start_date=datetime.utcnow(),
        maturity_date=maturity_date,
        last_yield_date=datetime.utcnow(),
        auto_compound=position_data.auto_compound,
        auto_renew=position_data.auto_renew
    )

    db.add(position)

    # Actualizar TVL del producto
    product.current_tvl = (product.current_tvl or Decimal("0")) + position_data.amount

    # Crear transacción de depósito
    transaction = EarnTransaction(
        transaction_number=EarnTransaction.generate_transaction_number(),
        position_id=position.id,
        user_id=current_user.id,
        transaction_type=EarnTransactionType.DEPOSIT,
        amount=position_data.amount,
        currency=product.currency,
        balance_after=position_data.amount,
        description=f"Depósito en {product.name}"
    )

    db.add(transaction)
    await db.commit()
    await db.refresh(position)

    logger.info(
        "Earn position created",
        extra={
            "position_id": str(position.id),
            "user_id": str(current_user.id),
            "product_id": str(product.id),
            "amount": str(position_data.amount)
        }
    )

    return EarnPositionResponse(
        **{k: v for k, v in position.__dict__.items() if not k.startswith("_")},
        current_value=position.current_value,
        total_yield=position.total_yield,
        is_mature=position.is_mature,
        product_name=product.name,
        product_type=product.product_type.value
    )


@router.get("/positions", response_model=EarnPositionList)
async def list_earn_positions(
    status_filter: Optional[EarnPositionStatus] = None,
    product_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar posiciones de rendimiento del usuario."""
    query = select(EarnPosition).where(EarnPosition.user_id == current_user.id)

    if status_filter:
        query = query.where(EarnPosition.status == status_filter)

    if product_id:
        query = query.where(EarnPosition.product_id == product_id)

    query = query.order_by(EarnPosition.created_at.desc())

    result = await db.execute(query)
    positions = result.scalars().all()

    total_value = sum(p.current_value for p in positions)
    total_yield = sum(p.total_yield for p in positions)

    by_status = {}
    for p in positions:
        status_key = p.status.value
        by_status[status_key] = by_status.get(status_key, 0) + 1

    return EarnPositionList(
        positions=[
            EarnPositionResponse(
                **{k: v for k, v in p.__dict__.items() if not k.startswith("_")},
                current_value=p.current_value,
                total_yield=p.total_yield,
                is_mature=p.is_mature
            )
            for p in positions
        ],
        total=len(positions),
        total_value=Decimal(str(total_value)),
        total_yield=Decimal(str(total_yield)),
        by_status=by_status
    )


@router.get("/positions/{position_id}", response_model=EarnPositionResponse)
async def get_earn_position(
    position_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener detalle de posición de rendimiento."""
    query = select(EarnPosition).where(
        EarnPosition.id == position_id,
        EarnPosition.user_id == current_user.id
    )

    result = await db.execute(query)
    position = result.scalar_one_or_none()

    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Posición no encontrada"
        )

    # Obtener producto
    product_query = select(EarnProduct).where(EarnProduct.id == position.product_id)
    product_result = await db.execute(product_query)
    product = product_result.scalar_one()

    return EarnPositionResponse(
        **{k: v for k, v in position.__dict__.items() if not k.startswith("_")},
        current_value=position.current_value,
        total_yield=position.total_yield,
        is_mature=position.is_mature,
        product_name=product.name,
        product_type=product.product_type.value
    )


@router.post("/positions/{position_id}/withdraw", response_model=EarnTransactionResponse)
async def withdraw_from_position(
    position_id: UUID,
    withdraw_data: EarnPositionWithdraw,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Retirar de posición de rendimiento."""
    query = select(EarnPosition).where(
        EarnPosition.id == position_id,
        EarnPosition.user_id == current_user.id,
        EarnPosition.status == EarnPositionStatus.ACTIVE
    )

    result = await db.execute(query)
    position = result.scalar_one_or_none()

    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Posición no encontrada o no activa"
        )

    # Obtener producto
    product_query = select(EarnProduct).where(EarnProduct.id == position.product_id)
    product_result = await db.execute(product_query)
    product = product_result.scalar_one()

    # Determinar monto a retirar
    if withdraw_data.withdraw_all:
        amount = Decimal(str(position.current_value))
    elif withdraw_data.withdraw_yield_only:
        amount = Decimal(str(position.total_yield))
    else:
        amount = withdraw_data.amount

    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay fondos para retirar"
        )

    if amount > position.current_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monto excede el balance disponible"
        )

    # Verificar si es retiro anticipado
    is_early = False
    penalty = Decimal("0")

    if position.maturity_date and datetime.utcnow() < position.maturity_date:
        is_early = True
        penalty = amount * (product.early_withdrawal_penalty / 100)
        amount = amount - penalty

    # Actualizar posición
    position.total_withdrawn = (position.total_withdrawn or Decimal("0")) + amount + penalty

    if withdraw_data.withdraw_all:
        position.status = EarnPositionStatus.WITHDRAWN
        position.withdrawn_at = datetime.utcnow()

    # Actualizar TVL
    product.current_tvl = (product.current_tvl or Decimal("0")) - (amount + penalty)

    # Crear transacción
    tx_type = EarnTransactionType.EARLY_WITHDRAWAL if is_early else EarnTransactionType.WITHDRAWAL

    transaction = EarnTransaction(
        transaction_number=EarnTransaction.generate_transaction_number(),
        position_id=position.id,
        user_id=current_user.id,
        transaction_type=tx_type,
        amount=amount,
        currency=position.currency,
        balance_after=Decimal(str(position.current_value)) - amount - penalty,
        description=f"Retiro de {product.name}" + (" (anticipado)" if is_early else "")
    )

    db.add(transaction)

    # Si hay penalización, crear transacción de penalización
    if penalty > 0:
        penalty_tx = EarnTransaction(
            transaction_number=EarnTransaction.generate_transaction_number(),
            position_id=position.id,
            user_id=current_user.id,
            transaction_type=EarnTransactionType.PENALTY,
            amount=penalty,
            currency=position.currency,
            description=f"Penalización por retiro anticipado ({product.early_withdrawal_penalty}%)"
        )
        db.add(penalty_tx)

    await db.commit()
    await db.refresh(transaction)

    return EarnTransactionResponse(**{k: v for k, v in transaction.__dict__.items() if not k.startswith("_")})


@router.patch("/positions/{position_id}", response_model=EarnPositionResponse)
async def update_earn_position(
    position_id: UUID,
    update_data: EarnPositionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Actualizar configuración de posición."""
    query = select(EarnPosition).where(
        EarnPosition.id == position_id,
        EarnPosition.user_id == current_user.id,
        EarnPosition.status == EarnPositionStatus.ACTIVE
    )

    result = await db.execute(query)
    position = result.scalar_one_or_none()

    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Posición no encontrada"
        )

    update_dict = update_data.dict(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(position, key, value)

    await db.commit()
    await db.refresh(position)

    return EarnPositionResponse(
        **{k: v for k, v in position.__dict__.items() if not k.startswith("_")},
        current_value=position.current_value,
        total_yield=position.total_yield,
        is_mature=position.is_mature
    )


# =====================
# Transactions
# =====================

@router.get("/transactions", response_model=EarnTransactionList)
async def list_earn_transactions(
    position_id: Optional[UUID] = None,
    transaction_type: Optional[EarnTransactionType] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar transacciones de Earn."""
    query = select(EarnTransaction).where(EarnTransaction.user_id == current_user.id)

    if position_id:
        query = query.where(EarnTransaction.position_id == position_id)

    if transaction_type:
        query = query.where(EarnTransaction.transaction_type == transaction_type)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(EarnTransaction.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    transactions = result.scalars().all()

    return EarnTransactionList(
        transactions=[
            EarnTransactionResponse(**{k: v for k, v in t.__dict__.items() if not k.startswith("_")})
            for t in transactions
        ],
        total=total,
        page=page,
        page_size=page_size
    )


# =====================
# Yield Distributions
# =====================

@router.get("/yields", response_model=YieldDistributionList)
async def list_yield_distributions(
    position_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar distribuciones de rendimiento."""
    query = select(YieldDistribution).where(
        YieldDistribution.user_id == current_user.id,
        YieldDistribution.status == YieldDistributionStatus.COMPLETED
    )

    if position_id:
        query = query.where(YieldDistribution.position_id == position_id)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Totals
    totals_query = select(
        func.sum(YieldDistribution.net_yield),
        func.sum(YieldDistribution.net_yield).filter(YieldDistribution.is_compounded == True),
        func.sum(YieldDistribution.net_yield).filter(YieldDistribution.is_withdrawn == True)
    ).where(
        YieldDistribution.user_id == current_user.id,
        YieldDistribution.status == YieldDistributionStatus.COMPLETED
    )
    totals_result = await db.execute(totals_query)
    totals = totals_result.one()

    # Paginate
    query = query.order_by(YieldDistribution.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    distributions = result.scalars().all()

    return YieldDistributionList(
        distributions=[
            YieldDistributionResponse(**{k: v for k, v in d.__dict__.items() if not k.startswith("_")})
            for d in distributions
        ],
        total=total,
        total_yield=totals[0] or Decimal("0"),
        total_compounded=totals[1] or Decimal("0"),
        total_withdrawn=totals[2] or Decimal("0")
    )


# =====================
# Promotions
# =====================

@router.get("/promotions", response_model=List[EarnPromotionResponse])
async def list_earn_promotions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar promociones activas de Earn."""
    now = datetime.utcnow()

    query = select(EarnPromotion).where(
        EarnPromotion.is_active == True,
        EarnPromotion.start_date <= now,
        EarnPromotion.end_date >= now
    )

    result = await db.execute(query)
    promotions = result.scalars().all()

    return [
        EarnPromotionResponse(
            **{k: v for k, v in p.__dict__.items() if not k.startswith("_")},
            is_available=True
        )
        for p in promotions
    ]


@router.post("/promotions/validate", response_model=EarnPromotionValidation)
async def validate_promotion(
    promo_data: EarnPromotionApply,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Validar código promocional."""
    now = datetime.utcnow()

    query = select(EarnPromotion).where(
        EarnPromotion.code == promo_data.promo_code.upper(),
        EarnPromotion.is_active == True,
        EarnPromotion.start_date <= now,
        EarnPromotion.end_date >= now
    )

    result = await db.execute(query)
    promotion = result.scalar_one_or_none()

    if not promotion:
        return EarnPromotionValidation(
            is_valid=False,
            promotion=None,
            error_message="Código promocional no válido o expirado"
        )

    # Verificar límites
    if promotion.max_uses_total and promotion.current_uses >= promotion.max_uses_total:
        return EarnPromotionValidation(
            is_valid=False,
            promotion=None,
            error_message="Promoción agotada"
        )

    return EarnPromotionValidation(
        is_valid=True,
        promotion=EarnPromotionResponse(**{k: v for k, v in promotion.__dict__.items() if not k.startswith("_")}),
        error_message=None,
        bonus_preview=promotion.bonus_value
    )


# =====================
# Analytics & Summary
# =====================

@router.get("/summary", response_model=EarnSummary)
async def get_earn_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener resumen de Earn para dashboard."""
    # Posiciones activas
    positions_query = select(EarnPosition).where(
        EarnPosition.user_id == current_user.id,
        EarnPosition.status == EarnPositionStatus.ACTIVE
    )
    result = await db.execute(positions_query)
    positions = result.scalars().all()

    total_balance = sum(p.current_value for p in positions)

    # Yield hoy
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    yield_today_query = select(func.sum(YieldDistribution.net_yield)).where(
        YieldDistribution.user_id == current_user.id,
        YieldDistribution.created_at >= today
    )
    yield_today = (await db.execute(yield_today_query)).scalar() or Decimal("0")

    # Yield mes
    month_start = today.replace(day=1)
    yield_month_query = select(func.sum(YieldDistribution.net_yield)).where(
        YieldDistribution.user_id == current_user.id,
        YieldDistribution.created_at >= month_start
    )
    yield_month = (await db.execute(yield_month_query)).scalar() or Decimal("0")

    # Yield total
    yield_total_query = select(func.sum(YieldDistribution.net_yield)).where(
        YieldDistribution.user_id == current_user.id
    )
    yield_total = (await db.execute(yield_total_query)).scalar() or Decimal("0")

    # Próxima madurez
    next_maturity = None
    for p in positions:
        if p.maturity_date and (next_maturity is None or p.maturity_date < next_maturity):
            next_maturity = p.maturity_date

    return EarnSummary(
        total_balance=Decimal(str(total_balance)),
        total_yield_today=yield_today,
        total_yield_month=yield_month,
        total_yield_all_time=yield_total,
        active_positions=len(positions),
        best_performing_product=None,
        best_apy=None,
        next_yield_payment=None,
        next_maturity=next_maturity
    )


@router.get("/analytics", response_model=EarnAnalytics)
async def get_earn_analytics(
    period: str = Query("year", regex="^(month|quarter|year|all)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener analíticas detalladas de Earn."""
    # Total depositado
    deposited_query = select(func.sum(EarnTransaction.amount)).where(
        EarnTransaction.user_id == current_user.id,
        EarnTransaction.transaction_type == EarnTransactionType.DEPOSIT
    )
    total_deposited = (await db.execute(deposited_query)).scalar() or Decimal("0")

    # Total yield
    yield_query = select(func.sum(EarnTransaction.amount)).where(
        EarnTransaction.user_id == current_user.id,
        EarnTransaction.transaction_type == EarnTransactionType.YIELD_PAYMENT
    )
    total_yield = (await db.execute(yield_query)).scalar() or Decimal("0")

    # Total retirado
    withdrawn_query = select(func.sum(EarnTransaction.amount)).where(
        EarnTransaction.user_id == current_user.id,
        EarnTransaction.transaction_type == EarnTransactionType.WITHDRAWAL
    )
    total_withdrawn = (await db.execute(withdrawn_query)).scalar() or Decimal("0")

    # Balance actual
    positions_query = select(EarnPosition).where(
        EarnPosition.user_id == current_user.id,
        EarnPosition.status == EarnPositionStatus.ACTIVE
    )
    result = await db.execute(positions_query)
    positions = result.scalars().all()
    current_balance = sum(p.current_value for p in positions)

    # APY promedio
    avg_apy = Decimal("0")
    if positions:
        total_weighted = sum(
            p.current_value * float(p.locked_apy or Decimal("0"))
            for p in positions
        )
        if current_balance > 0:
            avg_apy = Decimal(str(total_weighted / current_balance))

    return EarnAnalytics(
        total_deposited=total_deposited,
        total_yield_earned=total_yield,
        total_withdrawn=total_withdrawn,
        current_balance=Decimal(str(current_balance)),
        active_positions=len(positions),
        average_apy=avg_apy,
        yield_by_month=[],
        positions_by_product=[],
        yield_projections={}
    )


# =====================
# Calculator
# =====================

@router.post("/calculate", response_model=EarnCalculatorResponse)
async def calculate_yield(
    calc_data: EarnCalculatorRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Calcular rendimiento proyectado."""
    # Obtener producto
    query = select(EarnProduct).where(EarnProduct.id == calc_data.product_id)
    result = await db.execute(query)
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado"
        )

    amount = calc_data.amount
    term_days = calc_data.term_days or product.lock_period_days or 365
    apy = Decimal(str(product.current_apy))

    # Cálculos
    daily_rate = apy / 365 / 100

    yield_daily = amount * daily_rate
    yield_monthly = yield_daily * 30
    yield_yearly = amount * apy / 100
    yield_at_maturity = yield_daily * term_days

    # Simple
    final_simple = amount + yield_at_maturity

    # Compound (diario)
    if calc_data.compound:
        # A = P(1 + r/n)^(nt) donde n=365 (compuesto diario)
        compound_rate = 1 + float(daily_rate)
        final_compound = float(amount) * (compound_rate ** term_days)
        final_compound = Decimal(str(final_compound))
    else:
        final_compound = final_simple

    return EarnCalculatorResponse(
        product_name=product.name,
        initial_amount=amount,
        term_days=term_days,
        apy=apy,
        yield_daily=yield_daily,
        yield_monthly=yield_monthly,
        yield_yearly=yield_yearly,
        yield_at_maturity=yield_at_maturity,
        final_amount_simple=final_simple,
        final_amount_compound=final_compound,
        compound_benefit=final_compound - final_simple
    )
