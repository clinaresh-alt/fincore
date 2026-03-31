"""
Endpoints para Tarjeta de Débito FinCore.
Integración con emisor de tarjetas (BIN sponsor).
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
from app.models.debit_card import (
    DebitCard, CardTransaction, CardLimit, CardDispute, CardReward,
    CardStatus, CardType, CardNetwork, CardTransactionStatus, CardTransactionType
)
from app.schemas.debit_card import (
    DebitCardCreate, DebitCardResponse, DebitCardList, DebitCardUpdate,
    DebitCardActivate, DebitCardSetPIN, DebitCardChangePIN, DebitCardFreeze, DebitCardReport,
    CardTransactionResponse, CardTransactionList,
    CardLimitCreate, CardLimitResponse, CardLimitList,
    CardDisputeCreate, CardDisputeResponse, CardDisputeList,
    CardRewardResponse, CardRewardList, CardRewardsSummary,
    CardAnalytics, CardSecuritySummary
)
from app.infrastructure import get_logger

router = APIRouter(prefix="/cards", tags=["Debit Cards"])
logger = get_logger(__name__)


# =====================
# Cards
# =====================

@router.post("", response_model=DebitCardResponse, status_code=status.HTTP_201_CREATED)
async def request_debit_card(
    card_data: DebitCardCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Solicitar nueva tarjeta de débito.

    - Virtual: Disponible inmediatamente
    - Física: Requiere envío (3-5 días hábiles)
    """
    # Verificar KYC
    # if current_user.kyc_level < 2:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Se requiere KYC nivel 2 para solicitar tarjeta"
    #     )

    # Verificar límite de tarjetas
    cards_count_query = select(func.count(DebitCard.id)).where(
        DebitCard.user_id == current_user.id,
        DebitCard.status.notin_([CardStatus.CANCELLED, CardStatus.EXPIRED])
    )
    cards_count = (await db.execute(cards_count_query)).scalar() or 0

    if cards_count >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Máximo 5 tarjetas activas por usuario"
        )

    # Generar datos de tarjeta (en producción, esto viene del emisor)
    import secrets
    card_id = f"FC{secrets.token_hex(8).upper()}"
    card_token = DebitCard.generate_card_token()
    last_four = f"{secrets.randbelow(10000):04d}"

    # Calcular expiración (3 años)
    now = datetime.utcnow()
    expiry_year = now.year + 3
    expiry_month = now.month

    card = DebitCard(
        user_id=current_user.id,
        card_id=card_id,
        card_token=card_token,
        last_four=last_four,
        bin_number="45678901",  # BIN de FinCore
        card_type=card_data.card_type,
        card_network=card_data.card_network,
        status=CardStatus.PENDING if card_data.card_type == CardType.PHYSICAL else CardStatus.ACTIVE,
        cardholder_name=card_data.cardholder_name,
        expiry_month=expiry_month,
        expiry_year=expiry_year,
        shipping_address_id=card_data.shipping_address_id,
        is_contactless_enabled=card_data.is_contactless_enabled,
        is_online_enabled=card_data.is_online_enabled,
        is_atm_enabled=card_data.is_atm_enabled,
        is_international_enabled=card_data.is_international_enabled,
        daily_spend_limit=card_data.daily_spend_limit or Decimal("50000"),
        monthly_spend_limit=card_data.monthly_spend_limit or Decimal("200000"),
        single_transaction_limit=card_data.single_transaction_limit or Decimal("20000"),
        daily_atm_limit=card_data.daily_atm_limit or Decimal("10000")
    )

    if card_data.card_type == CardType.VIRTUAL:
        card.activated_at = datetime.utcnow()
    else:
        card.shipping_status = "ordered"

    db.add(card)
    await db.commit()
    await db.refresh(card)

    logger.info(
        "Debit card requested",
        extra={
            "card_id": str(card.id),
            "user_id": str(current_user.id),
            "card_type": card_data.card_type.value
        }
    )

    return DebitCardResponse(
        **{k: v for k, v in card.__dict__.items() if not k.startswith("_")},
        expiry_display=card.expiry_display,
        masked_number=card.masked_number
    )


@router.get("", response_model=DebitCardList)
async def list_debit_cards(
    include_cancelled: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar tarjetas de débito del usuario."""
    query = select(DebitCard).where(DebitCard.user_id == current_user.id)

    if not include_cancelled:
        query = query.where(DebitCard.status.notin_([CardStatus.CANCELLED]))

    query = query.order_by(DebitCard.created_at.desc())

    result = await db.execute(query)
    cards = result.scalars().all()

    active_count = len([c for c in cards if c.status == CardStatus.ACTIVE])
    virtual_count = len([c for c in cards if c.card_type == CardType.VIRTUAL])
    physical_count = len([c for c in cards if c.card_type == CardType.PHYSICAL])

    return DebitCardList(
        cards=[
            DebitCardResponse(
                **{k: v for k, v in c.__dict__.items() if not k.startswith("_")},
                expiry_display=c.expiry_display,
                masked_number=c.masked_number
            )
            for c in cards
        ],
        total=len(cards),
        active_count=active_count,
        virtual_count=virtual_count,
        physical_count=physical_count
    )


@router.get("/{card_id}", response_model=DebitCardResponse)
async def get_debit_card(
    card_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener detalle de tarjeta de débito."""
    query = select(DebitCard).where(
        DebitCard.id == card_id,
        DebitCard.user_id == current_user.id
    )

    result = await db.execute(query)
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarjeta no encontrada"
        )

    return DebitCardResponse(
        **{k: v for k, v in card.__dict__.items() if not k.startswith("_")},
        expiry_display=card.expiry_display,
        masked_number=card.masked_number
    )


@router.patch("/{card_id}", response_model=DebitCardResponse)
async def update_debit_card(
    card_id: UUID,
    update_data: DebitCardUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Actualizar configuración de tarjeta."""
    query = select(DebitCard).where(
        DebitCard.id == card_id,
        DebitCard.user_id == current_user.id,
        DebitCard.status.notin_([CardStatus.CANCELLED, CardStatus.EXPIRED])
    )

    result = await db.execute(query)
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarjeta no encontrada"
        )

    update_dict = update_data.dict(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(card, key, value)

    await db.commit()
    await db.refresh(card)

    return DebitCardResponse(
        **{k: v for k, v in card.__dict__.items() if not k.startswith("_")},
        expiry_display=card.expiry_display,
        masked_number=card.masked_number
    )


@router.post("/{card_id}/activate", response_model=DebitCardResponse)
async def activate_physical_card(
    card_id: UUID,
    activation_data: DebitCardActivate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Activar tarjeta física recibida."""
    query = select(DebitCard).where(
        DebitCard.id == card_id,
        DebitCard.user_id == current_user.id,
        DebitCard.card_type == CardType.PHYSICAL,
        DebitCard.status == CardStatus.PENDING
    )

    result = await db.execute(query)
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarjeta no encontrada o ya activada"
        )

    if card.last_four != activation_data.last_four:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los últimos 4 dígitos no coinciden"
        )

    card.status = CardStatus.ACTIVE
    card.activated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(card)

    logger.info("Physical card activated", extra={"card_id": str(card.id)})

    return DebitCardResponse(
        **{k: v for k, v in card.__dict__.items() if not k.startswith("_")},
        expiry_display=card.expiry_display,
        masked_number=card.masked_number
    )


@router.post("/{card_id}/pin", response_model=dict)
async def set_card_pin(
    card_id: UUID,
    pin_data: DebitCardSetPIN,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Establecer PIN de tarjeta."""
    query = select(DebitCard).where(
        DebitCard.id == card_id,
        DebitCard.user_id == current_user.id,
        DebitCard.status == CardStatus.ACTIVE
    )

    result = await db.execute(query)
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarjeta no encontrada o no activa"
        )

    # En producción, el PIN se envía al emisor de forma segura
    card.pin_set = True
    card.pin_attempts = 0

    await db.commit()

    return {"message": "PIN establecido correctamente"}


@router.post("/{card_id}/freeze", response_model=DebitCardResponse)
async def freeze_card(
    card_id: UUID,
    freeze_data: DebitCardFreeze,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Congelar tarjeta temporalmente."""
    query = select(DebitCard).where(
        DebitCard.id == card_id,
        DebitCard.user_id == current_user.id,
        DebitCard.status == CardStatus.ACTIVE
    )

    result = await db.execute(query)
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarjeta no encontrada o no activa"
        )

    card.status = CardStatus.FROZEN
    card.frozen_at = datetime.utcnow()

    await db.commit()
    await db.refresh(card)

    logger.info("Card frozen", extra={"card_id": str(card.id), "reason": freeze_data.reason})

    return DebitCardResponse(
        **{k: v for k, v in card.__dict__.items() if not k.startswith("_")},
        expiry_display=card.expiry_display,
        masked_number=card.masked_number
    )


@router.post("/{card_id}/unfreeze", response_model=DebitCardResponse)
async def unfreeze_card(
    card_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Descongelar tarjeta."""
    query = select(DebitCard).where(
        DebitCard.id == card_id,
        DebitCard.user_id == current_user.id,
        DebitCard.status == CardStatus.FROZEN
    )

    result = await db.execute(query)
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarjeta no encontrada o no congelada"
        )

    card.status = CardStatus.ACTIVE
    card.frozen_at = None

    await db.commit()
    await db.refresh(card)

    return DebitCardResponse(
        **{k: v for k, v in card.__dict__.items() if not k.startswith("_")},
        expiry_display=card.expiry_display,
        masked_number=card.masked_number
    )


@router.post("/{card_id}/report", response_model=DebitCardResponse)
async def report_card_lost_stolen(
    card_id: UUID,
    report_data: DebitCardReport,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Reportar tarjeta perdida o robada."""
    query = select(DebitCard).where(
        DebitCard.id == card_id,
        DebitCard.user_id == current_user.id,
        DebitCard.status.notin_([CardStatus.CANCELLED, CardStatus.LOST, CardStatus.STOLEN])
    )

    result = await db.execute(query)
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarjeta no encontrada"
        )

    card.status = CardStatus.LOST if report_data.report_type == "lost" else CardStatus.STOLEN
    card.cancelled_at = datetime.utcnow()

    await db.commit()
    await db.refresh(card)

    logger.warning(
        f"Card reported {report_data.report_type}",
        extra={"card_id": str(card.id), "user_id": str(current_user.id)}
    )

    # Si solicita reemplazo, crear nueva tarjeta automáticamente
    if report_data.request_replacement and card.card_type == CardType.PHYSICAL:
        # Lógica de reemplazo
        pass

    return DebitCardResponse(
        **{k: v for k, v in card.__dict__.items() if not k.startswith("_")},
        expiry_display=card.expiry_display,
        masked_number=card.masked_number
    )


@router.delete("/{card_id}")
async def cancel_card(
    card_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Cancelar tarjeta permanentemente."""
    query = select(DebitCard).where(
        DebitCard.id == card_id,
        DebitCard.user_id == current_user.id,
        DebitCard.status.notin_([CardStatus.CANCELLED])
    )

    result = await db.execute(query)
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarjeta no encontrada"
        )

    card.status = CardStatus.CANCELLED
    card.cancelled_at = datetime.utcnow()

    await db.commit()

    return {"message": "Tarjeta cancelada permanentemente"}


# =====================
# Transactions
# =====================

@router.get("/{card_id}/transactions", response_model=CardTransactionList)
async def list_card_transactions(
    card_id: UUID,
    status_filter: Optional[CardTransactionStatus] = None,
    transaction_type: Optional[CardTransactionType] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar transacciones de tarjeta."""
    # Verificar propiedad de la tarjeta
    card_query = select(DebitCard).where(
        DebitCard.id == card_id,
        DebitCard.user_id == current_user.id
    )
    card_result = await db.execute(card_query)
    card = card_result.scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarjeta no encontrada"
        )

    query = select(CardTransaction).where(CardTransaction.card_id == card_id)

    if status_filter:
        query = query.where(CardTransaction.status == status_filter)

    if transaction_type:
        query = query.where(CardTransaction.transaction_type == transaction_type)

    if start_date:
        query = query.where(CardTransaction.created_at >= start_date)

    if end_date:
        query = query.where(CardTransaction.created_at <= end_date)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Totals
    spent_query = select(func.sum(CardTransaction.amount)).where(
        CardTransaction.card_id == card_id,
        CardTransaction.status == CardTransactionStatus.CAPTURED,
        CardTransaction.transaction_type == CardTransactionType.PURCHASE
    )
    total_spent = (await db.execute(spent_query)).scalar() or Decimal("0")

    refunded_query = select(func.sum(CardTransaction.amount)).where(
        CardTransaction.card_id == card_id,
        CardTransaction.transaction_type == CardTransactionType.REFUND
    )
    total_refunded = (await db.execute(refunded_query)).scalar() or Decimal("0")

    # Paginate
    query = query.order_by(CardTransaction.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    transactions = result.scalars().all()

    return CardTransactionList(
        transactions=[
            CardTransactionResponse(**{k: v for k, v in t.__dict__.items() if not k.startswith("_")})
            for t in transactions
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_spent=total_spent,
        total_refunded=total_refunded
    )


# =====================
# Limits
# =====================

@router.post("/{card_id}/limits", response_model=CardLimitResponse, status_code=status.HTTP_201_CREATED)
async def create_card_limit(
    card_id: UUID,
    limit_data: CardLimitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Crear límite personalizado para tarjeta."""
    # Verificar propiedad
    card_query = select(DebitCard).where(
        DebitCard.id == card_id,
        DebitCard.user_id == current_user.id
    )
    card_result = await db.execute(card_query)
    card = card_result.scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarjeta no encontrada"
        )

    limit = CardLimit(
        card_id=card_id,
        limit_type=limit_data.limit_type,
        limit_identifier=limit_data.limit_identifier,
        action=limit_data.action,
        daily_limit=limit_data.daily_limit,
        monthly_limit=limit_data.monthly_limit,
        single_limit=limit_data.single_limit
    )

    db.add(limit)
    await db.commit()
    await db.refresh(limit)

    return CardLimitResponse(**{k: v for k, v in limit.__dict__.items() if not k.startswith("_")})


@router.get("/{card_id}/limits", response_model=CardLimitList)
async def list_card_limits(
    card_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar límites personalizados de tarjeta."""
    # Verificar propiedad
    card_query = select(DebitCard).where(
        DebitCard.id == card_id,
        DebitCard.user_id == current_user.id
    )
    card_result = await db.execute(card_query)
    card = card_result.scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarjeta no encontrada"
        )

    query = select(CardLimit).where(
        CardLimit.card_id == card_id,
        CardLimit.is_active == True
    )

    result = await db.execute(query)
    limits = result.scalars().all()

    return CardLimitList(
        limits=[
            CardLimitResponse(**{k: v for k, v in l.__dict__.items() if not k.startswith("_")})
            for l in limits
        ],
        total=len(limits)
    )


@router.delete("/{card_id}/limits/{limit_id}")
async def delete_card_limit(
    card_id: UUID,
    limit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Eliminar límite personalizado."""
    query = select(CardLimit).where(
        CardLimit.id == limit_id,
        CardLimit.card_id == card_id
    )

    result = await db.execute(query)
    limit = result.scalar_one_or_none()

    if not limit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Límite no encontrado"
        )

    limit.is_active = False
    await db.commit()

    return {"message": "Límite eliminado"}


# =====================
# Disputes
# =====================

@router.post("/disputes", response_model=CardDisputeResponse, status_code=status.HTTP_201_CREATED)
async def create_card_dispute(
    dispute_data: CardDisputeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Crear disputa de transacción."""
    # Verificar transacción
    tx_query = select(CardTransaction).where(
        CardTransaction.id == dispute_data.transaction_id,
        CardTransaction.user_id == current_user.id
    )
    tx_result = await db.execute(tx_query)
    transaction = tx_result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transacción no encontrada"
        )

    # Verificar que no haya disputa existente
    existing_query = select(CardDispute).where(
        CardDispute.transaction_id == dispute_data.transaction_id,
        CardDispute.status.notin_(["closed", "resolved_against"])
    )
    existing = (await db.execute(existing_query)).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una disputa para esta transacción"
        )

    dispute = CardDispute(
        dispute_number=CardDispute.generate_dispute_number(),
        transaction_id=transaction.id,
        user_id=current_user.id,
        reason_code=dispute_data.reason_code,
        reason_description=dispute_data.reason_description,
        user_description=dispute_data.user_description,
        disputed_amount=dispute_data.disputed_amount or transaction.amount,
        currency=transaction.currency,
        documents=dispute_data.documents or []
    )

    db.add(dispute)
    await db.commit()
    await db.refresh(dispute)

    logger.info("Card dispute created", extra={"dispute_id": str(dispute.id)})

    return CardDisputeResponse(**{k: v for k, v in dispute.__dict__.items() if not k.startswith("_")})


@router.get("/disputes", response_model=CardDisputeList)
async def list_card_disputes(
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar disputas del usuario."""
    query = select(CardDispute).where(CardDispute.user_id == current_user.id)

    if status_filter:
        query = query.where(CardDispute.status == status_filter)

    query = query.order_by(CardDispute.created_at.desc())

    result = await db.execute(query)
    disputes = result.scalars().all()

    open_count = len([d for d in disputes if d.status in ["open", "under_review"]])
    resolved_count = len([d for d in disputes if d.status.startswith("resolved")])

    return CardDisputeList(
        disputes=[
            CardDisputeResponse(**{k: v for k, v in d.__dict__.items() if not k.startswith("_")})
            for d in disputes
        ],
        total=len(disputes),
        open_count=open_count,
        resolved_count=resolved_count
    )


# =====================
# Rewards
# =====================

@router.get("/rewards", response_model=CardRewardList)
async def list_card_rewards(
    status_filter: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar recompensas de tarjeta."""
    query = select(CardReward).where(CardReward.user_id == current_user.id)

    if status_filter:
        query = query.where(CardReward.status == status_filter)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Totals
    pending_query = select(func.sum(CardReward.amount)).where(
        CardReward.user_id == current_user.id,
        CardReward.status == "pending"
    )
    total_pending = (await db.execute(pending_query)).scalar() or Decimal("0")

    credited_query = select(func.sum(CardReward.amount)).where(
        CardReward.user_id == current_user.id,
        CardReward.status == "credited"
    )
    total_credited = (await db.execute(credited_query)).scalar() or Decimal("0")

    expired_query = select(func.sum(CardReward.amount)).where(
        CardReward.user_id == current_user.id,
        CardReward.status == "expired"
    )
    total_expired = (await db.execute(expired_query)).scalar() or Decimal("0")

    # Paginate
    query = query.order_by(CardReward.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    rewards = result.scalars().all()

    return CardRewardList(
        rewards=[
            CardRewardResponse(**{k: v for k, v in r.__dict__.items() if not k.startswith("_")})
            for r in rewards
        ],
        total=total,
        total_pending=total_pending,
        total_credited=total_credited,
        total_expired=total_expired
    )


@router.get("/rewards/summary", response_model=CardRewardsSummary)
async def get_rewards_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener resumen de recompensas."""
    # Total earned
    earned_query = select(func.sum(CardReward.amount)).where(
        CardReward.user_id == current_user.id
    )
    total_earned = (await db.execute(earned_query)).scalar() or Decimal("0")

    # Pending
    pending_query = select(func.sum(CardReward.amount)).where(
        CardReward.user_id == current_user.id,
        CardReward.status == "pending"
    )
    total_pending = (await db.execute(pending_query)).scalar() or Decimal("0")

    # Redeemed (credited)
    redeemed_query = select(func.sum(CardReward.amount)).where(
        CardReward.user_id == current_user.id,
        CardReward.status == "credited"
    )
    total_redeemed = (await db.execute(redeemed_query)).scalar() or Decimal("0")

    return CardRewardsSummary(
        total_earned=total_earned,
        total_pending=total_pending,
        total_redeemed=total_redeemed,
        current_balance=total_pending,
        earning_rate=Decimal("0.01"),  # 1% cashback
        next_expiry=None,
        expiring_amount=None
    )


# =====================
# Analytics
# =====================

@router.get("/{card_id}/analytics", response_model=CardAnalytics)
async def get_card_analytics(
    card_id: UUID,
    period: str = Query("month", regex="^(week|month|year)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener analíticas de uso de tarjeta."""
    # Verificar propiedad
    card_query = select(DebitCard).where(
        DebitCard.id == card_id,
        DebitCard.user_id == current_user.id
    )
    card = (await db.execute(card_query)).scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarjeta no encontrada"
        )

    now = datetime.utcnow()
    if period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = now - timedelta(days=365)

    # Gasto total
    spent_query = select(func.sum(CardTransaction.amount)).where(
        CardTransaction.card_id == card_id,
        CardTransaction.status == CardTransactionStatus.CAPTURED,
        CardTransaction.transaction_type == CardTransactionType.PURCHASE,
        CardTransaction.created_at >= start_date
    )
    total_spent = (await db.execute(spent_query)).scalar() or Decimal("0")

    # Transacciones
    tx_count_query = select(func.count(CardTransaction.id)).where(
        CardTransaction.card_id == card_id,
        CardTransaction.created_at >= start_date
    )
    total_transactions = (await db.execute(tx_count_query)).scalar() or 0

    return CardAnalytics(
        total_spent_month=total_spent if period == "month" else Decimal("0"),
        total_spent_year=total_spent if period == "year" else Decimal("0"),
        total_transactions=total_transactions,
        average_transaction=total_spent / max(total_transactions, 1),
        spending_by_category=[],
        spending_by_merchant=[],
        spending_by_day=[],
        international_spending=Decimal("0"),
        online_spending=Decimal("0"),
        atm_withdrawals=Decimal("0"),
        rewards_earned=Decimal("0")
    )


@router.get("/{card_id}/security", response_model=CardSecuritySummary)
async def get_card_security_summary(
    card_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener resumen de seguridad de tarjeta."""
    query = select(DebitCard).where(
        DebitCard.id == card_id,
        DebitCard.user_id == current_user.id
    )

    card = (await db.execute(query)).scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarjeta no encontrada"
        )

    # Contar límites activos
    limits_query = select(func.count(CardLimit.id)).where(
        CardLimit.card_id == card_id,
        CardLimit.is_active == True
    )
    active_limits = (await db.execute(limits_query)).scalar() or 0

    # Transacciones declinadas recientes
    declined_query = select(func.count(CardTransaction.id)).where(
        CardTransaction.card_id == card_id,
        CardTransaction.status == CardTransactionStatus.DECLINED,
        CardTransaction.created_at >= datetime.utcnow() - timedelta(days=30)
    )
    blocked_attempts = (await db.execute(declined_query)).scalar() or 0

    return CardSecuritySummary(
        card_id=card.id,
        status=card.status,
        is_frozen=card.status == CardStatus.FROZEN,
        last_used_at=None,
        last_used_location=None,
        suspicious_transactions=0,
        blocked_attempts=blocked_attempts,
        active_limits=active_limits,
        international_enabled=card.is_international_enabled,
        online_enabled=card.is_online_enabled,
        contactless_enabled=card.is_contactless_enabled
    )
