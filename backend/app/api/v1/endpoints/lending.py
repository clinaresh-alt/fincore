"""
Endpoints para Préstamos con Colateral.
Sistema de lending con garantía en cripto/tokens.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID
from decimal import Decimal

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.lending import (
    LoanProduct, Loan, LoanCollateral, LoanPayment, LiquidationEvent, LoanOffer,
    LoanStatus, CollateralType, CollateralStatus, PaymentType
)
from app.schemas.lending import (
    LoanProductResponse, LoanProductList,
    LoanCreate, LoanResponse, LoanList, LoanSimulation, LoanSimulationResponse,
    CollateralDeposit, CollateralResponse, CollateralList, CollateralRelease,
    LoanPaymentCreate, LoanPaymentResponse, LoanPaymentList, PaymentSchedule,
    LiquidationEventResponse, LiquidationEventList,
    LoanOfferResponse, LoanOfferList, LoanOfferAccept,
    LendingAnalytics, LendingSummary, LoanHealthCheck, PortfolioHealthCheck
)
from app.infrastructure import get_logger

router = APIRouter(prefix="/lending", tags=["Lending"])
logger = get_logger(__name__)


# =====================
# Products
# =====================

@router.get("/products", response_model=LoanProductList)
async def list_loan_products(
    currency: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar productos de préstamo disponibles."""
    query = select(LoanProduct).where(LoanProduct.is_active == True)

    if currency:
        query = query.where(LoanProduct.loan_currency == currency)

    query = query.order_by(LoanProduct.interest_rate_annual)

    result = await db.execute(query)
    products = result.scalars().all()

    return LoanProductList(
        products=[
            LoanProductResponse(**{k: v for k, v in p.__dict__.items() if not k.startswith("_")})
            for p in products
        ],
        total=len(products)
    )


@router.get("/products/{product_id}", response_model=LoanProductResponse)
async def get_loan_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener detalle de producto de préstamo."""
    query = select(LoanProduct).where(LoanProduct.id == product_id)

    result = await db.execute(query)
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado"
        )

    return LoanProductResponse(**{k: v for k, v in product.__dict__.items() if not k.startswith("_")})


# =====================
# Loan Simulation
# =====================

@router.post("/simulate", response_model=LoanSimulationResponse)
async def simulate_loan(
    simulation: LoanSimulation,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Simular préstamo antes de solicitarlo."""
    # Obtener producto
    product_query = select(LoanProduct).where(
        LoanProduct.id == simulation.product_id,
        LoanProduct.is_active == True
    )
    product = (await db.execute(product_query)).scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado"
        )

    # Validar monto
    rejection_reasons = []

    if simulation.principal < product.min_loan_amount:
        rejection_reasons.append(f"Monto mínimo: {product.min_loan_amount} {product.loan_currency}")

    if product.max_loan_amount and simulation.principal > product.max_loan_amount:
        rejection_reasons.append(f"Monto máximo: {product.max_loan_amount} {product.loan_currency}")

    if simulation.term_days < product.min_term_days:
        rejection_reasons.append(f"Plazo mínimo: {product.min_term_days} días")

    if simulation.term_days > product.max_term_days:
        rejection_reasons.append(f"Plazo máximo: {product.max_term_days} días")

    # Verificar colateral aceptado
    if simulation.collateral_asset not in product.accepted_collaterals:
        rejection_reasons.append(f"Colateral {simulation.collateral_asset} no aceptado")

    # Calcular valor del colateral (precio simulado)
    collateral_prices = {
        "BTC": Decimal("60000"),
        "ETH": Decimal("3000"),
        "USDC": Decimal("1"),
        "USDT": Decimal("1")
    }
    collateral_price = collateral_prices.get(simulation.collateral_asset, Decimal("1"))
    collateral_value = simulation.collateral_amount * collateral_price

    # Calcular LTV inicial
    initial_ltv = (simulation.principal / collateral_value) * 100 if collateral_value > 0 else Decimal("999")

    if initial_ltv > product.initial_ltv:
        rejection_reasons.append(f"LTV inicial ({initial_ltv:.1f}%) excede máximo permitido ({product.initial_ltv}%)")

    # Cálculos de costos
    interest_rate = product.interest_rate_annual
    daily_rate = interest_rate / 365 / 100

    # Interés simple
    total_interest = simulation.principal * (interest_rate / 100) * (simulation.term_days / 365)
    origination_fee = simulation.principal * (product.origination_fee_percent / 100)
    total_cost = total_interest + origination_fee

    # Pagos
    if product.payment_frequency == "monthly":
        num_payments = max(simulation.term_days // 30, 1)
    elif product.payment_frequency == "weekly":
        num_payments = max(simulation.term_days // 7, 1)
    else:
        num_payments = max(simulation.term_days // 14, 1)

    payment_amount = (simulation.principal + total_interest) / num_payments

    # Precios de liquidación
    margin_call_price = (simulation.principal / (collateral_value * product.margin_call_ltv / 100)) * collateral_price
    liquidation_price = (simulation.principal / (collateral_value * product.liquidation_ltv / 100)) * collateral_price

    return LoanSimulationResponse(
        product_name=product.name,
        principal=simulation.principal,
        currency=product.loan_currency,
        term_days=simulation.term_days,
        interest_rate_annual=interest_rate,
        total_interest=total_interest,
        origination_fee=origination_fee,
        total_cost=total_cost,
        payment_frequency=product.payment_frequency,
        number_of_payments=num_payments,
        payment_amount=payment_amount,
        collateral_asset=simulation.collateral_asset,
        collateral_amount=simulation.collateral_amount,
        collateral_value_usd=collateral_value,
        initial_ltv=initial_ltv,
        margin_call_ltv=product.margin_call_ltv,
        liquidation_ltv=product.liquidation_ltv,
        collateral_price_at_margin_call=margin_call_price,
        collateral_price_at_liquidation=liquidation_price,
        is_eligible=len(rejection_reasons) == 0,
        rejection_reasons=rejection_reasons
    )


# =====================
# Loans
# =====================

@router.post("/loans", response_model=LoanResponse, status_code=status.HTTP_201_CREATED)
async def create_loan(
    loan_data: LoanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Crear solicitud de préstamo."""
    # Verificar KYC
    # if current_user.kyc_level < 2:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Se requiere KYC nivel 2 para solicitar préstamos"
    #     )

    # Obtener producto
    product_query = select(LoanProduct).where(
        LoanProduct.id == loan_data.product_id,
        LoanProduct.is_active == True
    )
    product = (await db.execute(product_query)).scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no disponible"
        )

    # Validaciones
    if loan_data.principal < product.min_loan_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Monto mínimo: {product.min_loan_amount} {product.loan_currency}"
        )

    if product.max_loan_amount and loan_data.principal > product.max_loan_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Monto máximo: {product.max_loan_amount} {product.loan_currency}"
        )

    # Verificar si usa oferta
    interest_rate = product.interest_rate_annual
    if loan_data.offer_code:
        offer_query = select(LoanOffer).where(
            LoanOffer.offer_code == loan_data.offer_code,
            LoanOffer.user_id == current_user.id,
            LoanOffer.is_active == True,
            LoanOffer.is_used == False,
            LoanOffer.valid_until >= datetime.utcnow()
        )
        offer = (await db.execute(offer_query)).scalar_one_or_none()

        if offer:
            interest_rate = offer.interest_rate

    # Calcular fee de originación
    origination_fee = loan_data.principal * (product.origination_fee_percent / 100)

    # Calcular número de pagos
    if product.payment_frequency == "monthly":
        payments_total = max(loan_data.term_days // 30, 1)
    elif product.payment_frequency == "weekly":
        payments_total = max(loan_data.term_days // 7, 1)
    else:
        payments_total = max(loan_data.term_days // 14, 1)

    loan = Loan(
        loan_number=Loan.generate_loan_number(),
        user_id=current_user.id,
        product_id=product.id,
        principal=loan_data.principal,
        currency=product.loan_currency,
        interest_rate=interest_rate,
        origination_fee=origination_fee,
        term_days=loan_data.term_days,
        status=LoanStatus.PENDING_COLLATERAL,
        outstanding_principal=loan_data.principal,
        payments_total=payments_total,
        auto_repay_enabled=loan_data.auto_repay_enabled
    )

    db.add(loan)
    await db.commit()
    await db.refresh(loan)

    logger.info(
        "Loan created",
        extra={
            "loan_id": str(loan.id),
            "user_id": str(current_user.id),
            "principal": str(loan_data.principal)
        }
    )

    return LoanResponse(
        **{k: v for k, v in loan.__dict__.items() if not k.startswith("_")},
        total_outstanding=loan.total_outstanding,
        product_name=product.name,
        product_code=product.code
    )


@router.get("/loans", response_model=LoanList)
async def list_loans(
    status_filter: Optional[LoanStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar préstamos del usuario."""
    query = select(Loan).where(Loan.user_id == current_user.id)

    if status_filter:
        query = query.where(Loan.status == status_filter)

    query = query.order_by(Loan.created_at.desc())

    result = await db.execute(query)
    loans = result.scalars().all()

    total_outstanding = sum(l.total_outstanding for l in loans if l.status == LoanStatus.ACTIVE)

    by_status = {}
    for l in loans:
        status_key = l.status.value
        by_status[status_key] = by_status.get(status_key, 0) + 1

    return LoanList(
        loans=[
            LoanResponse(
                **{k: v for k, v in l.__dict__.items() if not k.startswith("_")},
                total_outstanding=l.total_outstanding
            )
            for l in loans
        ],
        total=len(loans),
        total_outstanding=Decimal(str(total_outstanding)),
        by_status=by_status
    )


@router.get("/loans/{loan_id}", response_model=LoanResponse)
async def get_loan(
    loan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener detalle de préstamo."""
    query = select(Loan).where(
        Loan.id == loan_id,
        Loan.user_id == current_user.id
    )

    result = await db.execute(query)
    loan = result.scalar_one_or_none()

    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Préstamo no encontrado"
        )

    # Obtener producto
    product_query = select(LoanProduct).where(LoanProduct.id == loan.product_id)
    product = (await db.execute(product_query)).scalar_one()

    return LoanResponse(
        **{k: v for k, v in loan.__dict__.items() if not k.startswith("_")},
        total_outstanding=loan.total_outstanding,
        health_factor=loan.health_factor,
        product_name=product.name,
        product_code=product.code
    )


@router.post("/loans/{loan_id}/cancel")
async def cancel_loan(
    loan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Cancelar préstamo (solo en estado draft o pending_collateral)."""
    query = select(Loan).where(
        Loan.id == loan_id,
        Loan.user_id == current_user.id,
        Loan.status.in_([LoanStatus.DRAFT, LoanStatus.PENDING_COLLATERAL])
    )

    result = await db.execute(query)
    loan = result.scalar_one_or_none()

    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Préstamo no encontrado o no cancelable"
        )

    loan.status = LoanStatus.CANCELLED
    loan.closed_at = datetime.utcnow()

    await db.commit()

    return {"message": "Préstamo cancelado"}


# =====================
# Collateral
# =====================

@router.post("/loans/{loan_id}/collateral", response_model=CollateralResponse, status_code=status.HTTP_201_CREATED)
async def deposit_collateral(
    loan_id: UUID,
    collateral_data: CollateralDeposit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Depositar colateral para préstamo."""
    # Verificar préstamo
    loan_query = select(Loan).where(
        Loan.id == loan_id,
        Loan.user_id == current_user.id,
        Loan.status.in_([LoanStatus.PENDING_COLLATERAL, LoanStatus.ACTIVE, LoanStatus.MARGIN_CALL])
    )
    loan = (await db.execute(loan_query)).scalar_one_or_none()

    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Préstamo no encontrado o no acepta colateral"
        )

    # Obtener producto para verificar colateral aceptado
    product_query = select(LoanProduct).where(LoanProduct.id == loan.product_id)
    product = (await db.execute(product_query)).scalar_one()

    if collateral_data.asset_symbol not in product.accepted_collaterals:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Colateral {collateral_data.asset_symbol} no aceptado para este producto"
        )

    # Obtener precio actual (simulado)
    collateral_prices = {
        "BTC": Decimal("60000"),
        "ETH": Decimal("3000"),
        "USDC": Decimal("1"),
        "USDT": Decimal("1")
    }
    current_price = collateral_prices.get(collateral_data.asset_symbol, Decimal("1"))
    value_usd = collateral_data.amount * current_price

    collateral = LoanCollateral(
        loan_id=loan_id,
        user_id=current_user.id,
        collateral_type=collateral_data.collateral_type,
        asset_symbol=collateral_data.asset_symbol,
        asset_network=collateral_data.asset_network,
        amount=collateral_data.amount,
        price_at_deposit=current_price,
        value_usd_at_deposit=value_usd,
        current_price=current_price,
        current_value_usd=value_usd,
        last_price_update=datetime.utcnow(),
        status=CollateralStatus.LOCKED,
        locked_at=datetime.utcnow()
    )

    db.add(collateral)

    # Actualizar valor total del colateral en el préstamo
    loan.total_collateral_value_usd = (loan.total_collateral_value_usd or Decimal("0")) + value_usd

    # Calcular nuevo LTV
    if loan.total_collateral_value_usd > 0:
        loan.current_ltv = (loan.outstanding_principal / loan.total_collateral_value_usd) * 100
        loan.last_ltv_update = datetime.utcnow()

    # Si cumple con LTV inicial, cambiar estado
    if loan.status == LoanStatus.PENDING_COLLATERAL:
        if loan.current_ltv and loan.current_ltv <= product.initial_ltv:
            loan.status = LoanStatus.PENDING_APPROVAL
            # En producción habría un proceso de aprobación
            # Por simplicidad, aprobamos automáticamente
            loan.status = LoanStatus.ACTIVE
            loan.approved_at = datetime.utcnow()
            loan.disbursed_at = datetime.utcnow()
            loan.start_date = datetime.utcnow()
            loan.maturity_date = datetime.utcnow() + timedelta(days=loan.term_days)

            # Calcular próximo pago
            if product.payment_frequency == "monthly":
                loan.next_payment_date = datetime.utcnow() + timedelta(days=30)
            elif product.payment_frequency == "weekly":
                loan.next_payment_date = datetime.utcnow() + timedelta(days=7)
            else:
                loan.next_payment_date = datetime.utcnow() + timedelta(days=14)

            # Calcular monto de pago
            total_interest = loan.principal * (loan.interest_rate / 100) * (loan.term_days / 365)
            loan.next_payment_amount = (loan.principal + total_interest) / loan.payments_total

    # Si estaba en margin call, verificar si se resuelve
    if loan.status == LoanStatus.MARGIN_CALL:
        if loan.current_ltv and loan.current_ltv <= product.margin_call_ltv:
            loan.status = LoanStatus.ACTIVE
            loan.is_margin_call = False
            loan.margin_call_at = None
            loan.margin_call_deadline = None

    await db.commit()
    await db.refresh(collateral)

    logger.info(
        "Collateral deposited",
        extra={
            "loan_id": str(loan_id),
            "collateral_id": str(collateral.id),
            "amount": str(collateral_data.amount),
            "asset": collateral_data.asset_symbol
        }
    )

    return CollateralResponse(**{k: v for k, v in collateral.__dict__.items() if not k.startswith("_")})


@router.get("/loans/{loan_id}/collateral", response_model=CollateralList)
async def list_loan_collateral(
    loan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar colateral de un préstamo."""
    # Verificar préstamo
    loan_query = select(Loan).where(
        Loan.id == loan_id,
        Loan.user_id == current_user.id
    )
    loan = (await db.execute(loan_query)).scalar_one_or_none()

    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Préstamo no encontrado"
        )

    query = select(LoanCollateral).where(LoanCollateral.loan_id == loan_id)
    result = await db.execute(query)
    collaterals = result.scalars().all()

    total_value = sum(float(c.current_value_usd or 0) for c in collaterals)

    by_asset = {}
    for c in collaterals:
        by_asset[c.asset_symbol] = by_asset.get(c.asset_symbol, Decimal("0")) + (c.current_value_usd or Decimal("0"))

    return CollateralList(
        collaterals=[
            CollateralResponse(
                **{k: v for k, v in c.__dict__.items() if not k.startswith("_")},
                amount_locked=c.amount_locked
            )
            for c in collaterals
        ],
        total=len(collaterals),
        total_value_usd=Decimal(str(total_value)),
        by_asset=by_asset
    )


@router.post("/loans/{loan_id}/collateral/release", response_model=CollateralResponse)
async def release_collateral(
    loan_id: UUID,
    release_data: CollateralRelease,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Solicitar liberación de colateral excedente."""
    # Verificar préstamo activo
    loan_query = select(Loan).where(
        Loan.id == loan_id,
        Loan.user_id == current_user.id,
        Loan.status == LoanStatus.ACTIVE
    )
    loan = (await db.execute(loan_query)).scalar_one_or_none()

    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Préstamo no encontrado o no activo"
        )

    # Obtener producto
    product_query = select(LoanProduct).where(LoanProduct.id == loan.product_id)
    product = (await db.execute(product_query)).scalar_one()

    # Verificar colateral
    collateral_query = select(LoanCollateral).where(
        LoanCollateral.id == release_data.collateral_id,
        LoanCollateral.loan_id == loan_id,
        LoanCollateral.status == CollateralStatus.LOCKED
    )
    collateral = (await db.execute(collateral_query)).scalar_one_or_none()

    if not collateral:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Colateral no encontrado"
        )

    # Calcular monto a liberar
    release_amount = release_data.amount if not release_data.release_all else Decimal(str(collateral.amount_locked))

    if release_amount > collateral.amount_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monto excede el colateral disponible"
        )

    # Calcular nuevo valor total después de liberar
    release_value = release_amount * (collateral.current_price or collateral.price_at_deposit)
    new_total_value = (loan.total_collateral_value_usd or Decimal("0")) - release_value

    # Calcular nuevo LTV
    if new_total_value > 0:
        new_ltv = (loan.outstanding_principal / new_total_value) * 100
    else:
        new_ltv = Decimal("999")

    # Verificar que no exceda el LTV máximo
    if new_ltv > product.initial_ltv:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede liberar. LTV resultante ({new_ltv:.1f}%) excede máximo permitido ({product.initial_ltv}%)"
        )

    # Actualizar colateral
    collateral.amount_released = (collateral.amount_released or Decimal("0")) + release_amount

    if collateral.amount_locked <= 0:
        collateral.status = CollateralStatus.RELEASED
        collateral.released_at = datetime.utcnow()
    else:
        collateral.status = CollateralStatus.PARTIALLY_RELEASED

    # Actualizar préstamo
    loan.total_collateral_value_usd = new_total_value
    loan.current_ltv = new_ltv
    loan.last_ltv_update = datetime.utcnow()

    await db.commit()
    await db.refresh(collateral)

    return CollateralResponse(
        **{k: v for k, v in collateral.__dict__.items() if not k.startswith("_")},
        amount_locked=collateral.amount_locked
    )


# =====================
# Payments
# =====================

@router.post("/loans/{loan_id}/payments", response_model=LoanPaymentResponse, status_code=status.HTTP_201_CREATED)
async def make_loan_payment(
    loan_id: UUID,
    payment_data: LoanPaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Realizar pago de préstamo."""
    # Verificar préstamo
    loan_query = select(Loan).where(
        Loan.id == loan_id,
        Loan.user_id == current_user.id,
        Loan.status.in_([LoanStatus.ACTIVE, LoanStatus.MARGIN_CALL])
    )
    loan = (await db.execute(loan_query)).scalar_one_or_none()

    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Préstamo no encontrado o no activo"
        )

    # Validar monto
    if payment_data.amount > loan.total_outstanding:
        payment_data.amount = Decimal(str(loan.total_outstanding))

    # Distribuir pago entre interés y principal
    interest_payment = min(payment_data.amount, loan.accrued_interest or Decimal("0"))
    principal_payment = payment_data.amount - interest_payment

    # Determinar si es pago tardío
    is_late = False
    days_late = 0
    if loan.next_payment_date and datetime.utcnow() > loan.next_payment_date:
        is_late = True
        days_late = (datetime.utcnow() - loan.next_payment_date).days

    payment = LoanPayment(
        payment_number=LoanPayment.generate_payment_number(),
        loan_id=loan_id,
        user_id=current_user.id,
        payment_type=payment_data.payment_type,
        total_amount=payment_data.amount,
        principal_amount=principal_payment,
        interest_amount=interest_payment,
        fee_amount=Decimal("0"),
        currency=loan.currency,
        installment_number=loan.payments_made + 1,
        scheduled_date=loan.next_payment_date,
        is_late=is_late,
        days_late=days_late,
        payment_method=payment_data.payment_method,
        status="completed",
        processed_at=datetime.utcnow()
    )

    # Actualizar préstamo
    loan.outstanding_principal = (loan.outstanding_principal or Decimal("0")) - principal_payment
    loan.accrued_interest = (loan.accrued_interest or Decimal("0")) - interest_payment
    loan.total_paid = (loan.total_paid or Decimal("0")) + payment_data.amount
    loan.total_interest_paid = (loan.total_interest_paid or Decimal("0")) + interest_payment
    loan.payments_made = (loan.payments_made or 0) + 1

    payment.principal_after = loan.outstanding_principal
    payment.interest_after = loan.accrued_interest

    # Verificar si el préstamo está pagado
    if loan.total_outstanding <= 0.01:  # Tolerancia para decimales
        loan.status = LoanStatus.REPAID
        loan.closed_at = datetime.utcnow()
        loan.outstanding_principal = Decimal("0")
        loan.accrued_interest = Decimal("0")
    else:
        # Calcular próximo pago
        product_query = select(LoanProduct).where(LoanProduct.id == loan.product_id)
        product = (await db.execute(product_query)).scalar_one()

        if product.payment_frequency == "monthly":
            loan.next_payment_date = datetime.utcnow() + timedelta(days=30)
        elif product.payment_frequency == "weekly":
            loan.next_payment_date = datetime.utcnow() + timedelta(days=7)
        else:
            loan.next_payment_date = datetime.utcnow() + timedelta(days=14)

    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    logger.info(
        "Loan payment made",
        extra={
            "loan_id": str(loan_id),
            "payment_id": str(payment.id),
            "amount": str(payment_data.amount)
        }
    )

    return LoanPaymentResponse(**{k: v for k, v in payment.__dict__.items() if not k.startswith("_")})


@router.get("/loans/{loan_id}/payments", response_model=LoanPaymentList)
async def list_loan_payments(
    loan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar pagos de un préstamo."""
    # Verificar préstamo
    loan_query = select(Loan).where(
        Loan.id == loan_id,
        Loan.user_id == current_user.id
    )
    loan = (await db.execute(loan_query)).scalar_one_or_none()

    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Préstamo no encontrado"
        )

    query = select(LoanPayment).where(LoanPayment.loan_id == loan_id)
    query = query.order_by(LoanPayment.created_at.desc())

    result = await db.execute(query)
    payments = result.scalars().all()

    total_paid = sum(p.total_amount for p in payments)
    total_principal = sum(p.principal_amount for p in payments)
    total_interest = sum(p.interest_amount for p in payments)

    return LoanPaymentList(
        payments=[
            LoanPaymentResponse(**{k: v for k, v in p.__dict__.items() if not k.startswith("_")})
            for p in payments
        ],
        total=len(payments),
        total_paid=total_paid,
        total_principal_paid=total_principal,
        total_interest_paid=total_interest
    )


@router.get("/loans/{loan_id}/schedule", response_model=PaymentSchedule)
async def get_payment_schedule(
    loan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener calendario de pagos del préstamo."""
    # Verificar préstamo
    loan_query = select(Loan).where(
        Loan.id == loan_id,
        Loan.user_id == current_user.id
    )
    loan = (await db.execute(loan_query)).scalar_one_or_none()

    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Préstamo no encontrado"
        )

    # Obtener producto
    product_query = select(LoanProduct).where(LoanProduct.id == loan.product_id)
    product = (await db.execute(product_query)).scalar_one()

    # Calcular calendario
    payments = []
    remaining_principal = loan.outstanding_principal or loan.principal
    total_interest_calc = loan.principal * (loan.interest_rate / 100) * (loan.term_days / 365)
    payment_amount = (loan.principal + total_interest_calc) / (loan.payments_total or 1)

    if product.payment_frequency == "monthly":
        interval_days = 30
    elif product.payment_frequency == "weekly":
        interval_days = 7
    else:
        interval_days = 14

    start_date = loan.start_date or datetime.utcnow()

    for i in range(loan.payments_made or 0, loan.payments_total or 0):
        payment_date = start_date + timedelta(days=interval_days * (i + 1))

        # Calcular interés y principal para este pago
        interest_portion = remaining_principal * (loan.interest_rate / 100) * (interval_days / 365)
        principal_portion = payment_amount - interest_portion

        if principal_portion > remaining_principal:
            principal_portion = remaining_principal
            payment_amount = principal_portion + interest_portion

        payments.append({
            "number": i + 1,
            "date": payment_date.isoformat(),
            "principal": float(principal_portion),
            "interest": float(interest_portion),
            "total": float(payment_amount),
            "remaining_principal": float(remaining_principal - principal_portion),
            "status": "paid" if i < (loan.payments_made or 0) else "pending"
        })

        remaining_principal -= principal_portion

    total_principal = sum(p["principal"] for p in payments)
    total_interest = sum(p["interest"] for p in payments)
    total_amount = sum(p["total"] for p in payments)

    return PaymentSchedule(
        loan_id=loan.id,
        loan_number=loan.loan_number,
        payments=payments,
        total_principal=Decimal(str(total_principal)),
        total_interest=Decimal(str(total_interest)),
        total_amount=Decimal(str(total_amount))
    )


# =====================
# Health Check
# =====================

@router.get("/loans/{loan_id}/health", response_model=LoanHealthCheck)
async def get_loan_health(
    loan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Verificar salud de préstamo."""
    loan_query = select(Loan).where(
        Loan.id == loan_id,
        Loan.user_id == current_user.id
    )
    loan = (await db.execute(loan_query)).scalar_one_or_none()

    if not loan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Préstamo no encontrado"
        )

    product_query = select(LoanProduct).where(LoanProduct.id == loan.product_id)
    product = (await db.execute(product_query)).scalar_one()

    current_ltv = loan.current_ltv or Decimal("0")
    health_factor = Decimal(str(loan.health_factor)) if loan.health_factor else Decimal("1")

    # Determinar estado de salud
    if current_ltv >= product.liquidation_ltv:
        health_status = "critical"
    elif current_ltv >= product.margin_call_ltv:
        health_status = "warning"
    else:
        health_status = "healthy"

    # Calcular buffers
    ltv_to_margin = product.margin_call_ltv - current_ltv
    ltv_to_liquidation = product.liquidation_ltv - current_ltv

    # Calcular caída de precio para margin call y liquidación
    if loan.total_collateral_value_usd and loan.total_collateral_value_usd > 0:
        drop_to_margin = (1 - float(loan.outstanding_principal) / (float(loan.total_collateral_value_usd) * float(product.margin_call_ltv) / 100)) * 100
        drop_to_liquidation = (1 - float(loan.outstanding_principal) / (float(loan.total_collateral_value_usd) * float(product.liquidation_ltv) / 100)) * 100
    else:
        drop_to_margin = Decimal("0")
        drop_to_liquidation = Decimal("0")

    # Recomendaciones
    recommendations = []
    if health_status == "critical":
        recommendations.append("Deposite colateral adicional inmediatamente para evitar liquidación")
        recommendations.append("Considere realizar un pago parcial del préstamo")
    elif health_status == "warning":
        recommendations.append("Considere depositar colateral adicional")
        recommendations.append("Monitoree el precio de su colateral de cerca")
    else:
        recommendations.append("Su préstamo está en buen estado")

    return LoanHealthCheck(
        loan_id=loan.id,
        loan_number=loan.loan_number,
        status=loan.status,
        current_ltv=current_ltv,
        margin_call_ltv=product.margin_call_ltv,
        liquidation_ltv=product.liquidation_ltv,
        health_factor=health_factor,
        health_status=health_status,
        ltv_buffer_to_margin_call=ltv_to_margin,
        ltv_buffer_to_liquidation=ltv_to_liquidation,
        collateral_drop_to_margin_call=Decimal(str(max(drop_to_margin, 0))),
        collateral_drop_to_liquidation=Decimal(str(max(drop_to_liquidation, 0))),
        recommendations=recommendations
    )


# =====================
# Offers
# =====================

@router.get("/offers", response_model=LoanOfferList)
async def list_loan_offers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar ofertas de préstamo pre-aprobadas."""
    query = select(LoanOffer).where(
        LoanOffer.user_id == current_user.id,
        LoanOffer.valid_until >= datetime.utcnow()
    )
    query = query.order_by(LoanOffer.created_at.desc())

    result = await db.execute(query)
    offers = result.scalars().all()

    active_count = len([o for o in offers if o.is_active and not o.is_used])

    return LoanOfferList(
        offers=[
            LoanOfferResponse(**{k: v for k, v in o.__dict__.items() if not k.startswith("_")})
            for o in offers
        ],
        total=len(offers),
        active_count=active_count
    )


# =====================
# Summary & Analytics
# =====================

@router.get("/summary", response_model=LendingSummary)
async def get_lending_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener resumen de préstamos para dashboard."""
    # Préstamos activos
    loans_query = select(Loan).where(
        Loan.user_id == current_user.id,
        Loan.status == LoanStatus.ACTIVE
    )
    result = await db.execute(loans_query)
    active_loans = result.scalars().all()

    total_outstanding = sum(l.total_outstanding for l in active_loans)
    total_collateral = sum(float(l.total_collateral_value_usd or 0) for l in active_loans)

    # Próximo pago
    next_payment_date = None
    next_payment_amount = None
    for l in active_loans:
        if l.next_payment_date:
            if next_payment_date is None or l.next_payment_date < next_payment_date:
                next_payment_date = l.next_payment_date
                next_payment_amount = l.next_payment_amount

    # Health factor promedio
    health_factors = [l.health_factor for l in active_loans if l.health_factor]
    avg_health = sum(health_factors) / len(health_factors) if health_factors else None

    # Préstamos en riesgo
    loans_at_risk = len([l for l in active_loans if l.is_margin_call])

    return LendingSummary(
        active_loans=len(active_loans),
        total_outstanding=Decimal(str(total_outstanding)),
        next_payment_date=next_payment_date,
        next_payment_amount=next_payment_amount,
        total_collateral_value=Decimal(str(total_collateral)),
        average_health_factor=Decimal(str(avg_health)) if avg_health else None,
        loans_at_risk=loans_at_risk,
        available_credit=Decimal("0")  # Calcular basado en colateral disponible
    )


@router.get("/analytics", response_model=LendingAnalytics)
async def get_lending_analytics(
    period: str = Query("year", regex="^(month|quarter|year|all)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener analíticas de préstamos."""
    # Total borrowed
    borrowed_query = select(func.sum(Loan.principal)).where(
        Loan.user_id == current_user.id,
        Loan.status.notin_([LoanStatus.DRAFT, LoanStatus.CANCELLED])
    )
    total_borrowed = (await db.execute(borrowed_query)).scalar() or Decimal("0")

    # Outstanding
    outstanding_query = select(func.sum(Loan.outstanding_principal)).where(
        Loan.user_id == current_user.id,
        Loan.status == LoanStatus.ACTIVE
    )
    total_outstanding = (await db.execute(outstanding_query)).scalar() or Decimal("0")

    # Paid
    paid_query = select(func.sum(Loan.total_paid)).where(
        Loan.user_id == current_user.id
    )
    total_paid = (await db.execute(paid_query)).scalar() or Decimal("0")

    # Interest paid
    interest_query = select(func.sum(Loan.total_interest_paid)).where(
        Loan.user_id == current_user.id
    )
    total_interest = (await db.execute(interest_query)).scalar() or Decimal("0")

    # Active loans
    active_query = select(func.count(Loan.id)).where(
        Loan.user_id == current_user.id,
        Loan.status == LoanStatus.ACTIVE
    )
    active_loans = (await db.execute(active_query)).scalar() or 0

    # Collateral value
    collateral_query = select(func.sum(Loan.total_collateral_value_usd)).where(
        Loan.user_id == current_user.id,
        Loan.status == LoanStatus.ACTIVE
    )
    total_collateral = (await db.execute(collateral_query)).scalar() or Decimal("0")

    # Average LTV
    ltv_query = select(func.avg(Loan.current_ltv)).where(
        Loan.user_id == current_user.id,
        Loan.status == LoanStatus.ACTIVE
    )
    avg_ltv = (await db.execute(ltv_query)).scalar() or Decimal("0")

    # Average interest rate
    rate_query = select(func.avg(Loan.interest_rate)).where(
        Loan.user_id == current_user.id,
        Loan.status == LoanStatus.ACTIVE
    )
    avg_rate = (await db.execute(rate_query)).scalar() or Decimal("0")

    return LendingAnalytics(
        total_borrowed=total_borrowed,
        total_outstanding=total_outstanding,
        total_paid=total_paid,
        total_interest_paid=total_interest,
        active_loans=active_loans,
        average_interest_rate=avg_rate,
        total_collateral_value=total_collateral,
        average_ltv=avg_ltv,
        payment_history=[],
        ltv_history=[]
    )
