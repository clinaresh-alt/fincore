"""
Endpoints de Remesas para FinCore API.

Endpoints:
- POST /remittances/quote - Obtener cotizacion
- POST /remittances - Crear remesa
- GET /remittances - Listar remesas del usuario
- GET /remittances/{id} - Obtener remesa por ID
- POST /remittances/{id}/lock - Bloquear fondos en escrow
- POST /remittances/{id}/release - Liberar fondos (operador)
- POST /remittances/{id}/cancel - Cancelar remesa
- GET /remittances/limits - Obtener limites del usuario
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole
from app.models.remittance import Remittance, RemittanceStatus
from app.services.remittance_service import RemittanceService
from app.schemas.remittance import (
    QuoteRequest,
    QuoteResponse,
    CreateRemittanceRequest,
    RemittanceCreatedResponse,
    RemittanceResponse,
    RemittanceListResponse,
    LockFundsRequest,
    ReleaseFundsRequest,
    TransactionResponse,
    RemittanceLimitResponse,
    RemittanceStatusEnum,
    CurrencyEnum,
)

router = APIRouter(prefix="/remittances", tags=["Remittances"])


# ============ Dependencias ============

async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """Obtiene el usuario actual del token JWT."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autorizacion requerido"
        )

    token = auth_header.split(" ")[1]
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o expirado"
        )

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User no encontrado"
        )

    return user


async def get_operator_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Verifica que el usuario sea operador o admin."""
    if current_user.rol not in [UserRole.Admin, UserRole.Auditor]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos de operador requeridos"
        )
    return current_user


# ============ Endpoints Publicos ============

@router.post("/quote", response_model=QuoteResponse)
async def get_quote(
    request: QuoteRequest,
    db: Session = Depends(get_db),
):
    """
    Obtiene cotizacion para una remesa.

    No requiere autenticacion. Muestra tasas de cambio,
    comisiones y monto final estimado.
    """
    service = RemittanceService(db)

    quote = await service.get_quote(
        amount_source=request.amount_source,
        currency_source=request.currency_source,
        currency_destination=request.currency_destination,
    )

    return QuoteResponse(
        quote_id=quote.quote_id,
        amount_source=quote.amount_source,
        currency_source=quote.currency_source,
        amount_destination=quote.amount_destination,
        currency_destination=quote.currency_destination,
        amount_stablecoin=quote.amount_stablecoin,
        exchange_rate_source_usd=quote.exchange_rate_source_usd,
        exchange_rate_usd_destination=quote.exchange_rate_usd_destination,
        platform_fee=quote.platform_fee,
        network_fee=quote.network_fee,
        total_fees=quote.total_fees,
        total_to_pay=quote.total_to_pay,
        estimated_delivery=quote.estimated_delivery,
        quote_expires_at=quote.quote_expires_at,
    )


# ============ Endpoints de User ============

@router.post("", response_model=RemittanceCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_remittance(
    request: CreateRemittanceRequest,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Crea una nueva remesa.

    Requiere:
    - User autenticado con KYC aprobado
    - Datos completos del beneficiario
    - Monto dentro de limites permitidos
    """
    service = RemittanceService(db)

    # Obtener IP del cliente
    client_ip = req.client.host if req.client else None

    result = await service.create_remittance(
        sender_id=str(current_user.id),
        recipient_info=request.recipient_info.model_dump(),
        amount_source=request.amount_source,
        currency_source=request.currency_source,
        currency_destination=request.currency_destination,
        payment_method=request.payment_method,
        disbursement_method=request.disbursement_method,
        sender_ip=client_ip,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return RemittanceCreatedResponse(
        success=True,
        remittance_id=result.remittance_id,
        reference_code=result.reference_code,
        status=RemittanceStatusEnum(result.status.value) if result.status else None,
        message="Remesa creada exitosamente",
        next_steps=[
            f"1. Deposita {request.amount_source} {request.currency_source.value} usando {request.payment_method.value}",
            "2. Una vez confirmado el deposito, los fondos se bloquearan en escrow",
            "3. El beneficiario recibira los fondos en menos de 10 minutos",
        ]
    )


@router.get("", response_model=RemittanceListResponse)
async def list_remittances(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[RemittanceStatusEnum] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lista las remesas del usuario autenticado.
    """
    service = RemittanceService(db)
    offset = (page - 1) * page_size

    # Convertir enum de schema a enum de modelo si existe
    model_status = None
    if status_filter:
        model_status = RemittanceStatus(status_filter.value)

    remittances = service.get_user_remittances(
        user_id=str(current_user.id),
        limit=page_size + 1,  # +1 para saber si hay mas
        offset=offset,
        status=model_status,
    )

    has_more = len(remittances) > page_size
    items = remittances[:page_size]

    # Contar total
    total_query = db.query(Remittance).filter(
        Remittance.sender_id == current_user.id
    )
    if model_status:
        total_query = total_query.filter(Remittance.status == model_status)
    total = total_query.count()

    return RemittanceListResponse(
        items=[
            RemittanceResponse(
                id=str(r.id),
                reference_code=r.reference_code,
                status=RemittanceStatusEnum(r.status.value),
                recipient_info=r.recipient_info,
                amount_fiat_source=r.amount_fiat_source,
                currency_source=CurrencyEnum(r.currency_source.value),
                amount_fiat_destination=r.amount_fiat_destination,
                currency_destination=CurrencyEnum(r.currency_destination.value),
                amount_stablecoin=r.amount_stablecoin,
                stablecoin=r.stablecoin,
                exchange_rate_source_usd=r.exchange_rate_source_usd,
                platform_fee=r.platform_fee,
                network_fee=r.network_fee,
                total_fees=r.total_fees,
                payment_method=r.payment_method,
                disbursement_method=r.disbursement_method,
                escrow_locked_at=r.escrow_locked_at,
                escrow_expires_at=r.escrow_expires_at,
                created_at=r.created_at,
                updated_at=r.updated_at,
                completed_at=r.completed_at,
            )
            for r in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@router.get("/limits", response_model=RemittanceLimitResponse)
async def get_user_limits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Obtiene los limites de remesas del usuario actual.

    Incluye:
    - Limite diario y mensual
    - Monto usado hoy y este mes
    - Monto disponible
    """
    service = RemittanceService(db)
    limits = service.get_user_limits(str(current_user.id))

    return RemittanceLimitResponse(
        daily_limit=limits.get("daily_limit", 10000),
        monthly_limit=limits.get("monthly_limit", 50000),
        used_today=limits.get("used_today", 0),
        used_this_month=limits.get("used_this_month", 0),
        available_today=limits.get("available_today", 10000),
        available_this_month=limits.get("available_this_month", 50000),
        kyc_level=limits.get("kyc_level", "basic"),
    )


@router.get("/{remittance_id}", response_model=RemittanceResponse)
async def get_remittance(
    remittance_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Obtiene detalles de una remesa por ID.
    """
    service = RemittanceService(db)
    remittance = service.get_remittance(remittance_id)

    if not remittance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remesa no encontrada"
        )

    # Verificar que pertenece al usuario (o es admin)
    if str(remittance.sender_id) != str(current_user.id) and current_user.rol != UserRole.Admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta remesa"
        )

    return RemittanceResponse(
        id=str(remittance.id),
        reference_code=remittance.reference_code,
        status=RemittanceStatusEnum(remittance.status.value),
        recipient_info=remittance.recipient_info,
        amount_fiat_source=remittance.amount_fiat_source,
        currency_source=CurrencyEnum(remittance.currency_source.value),
        amount_fiat_destination=remittance.amount_fiat_destination,
        currency_destination=CurrencyEnum(remittance.currency_destination.value),
        amount_stablecoin=remittance.amount_stablecoin,
        stablecoin=remittance.stablecoin,
        exchange_rate_source_usd=remittance.exchange_rate_source_usd,
        platform_fee=remittance.platform_fee,
        network_fee=remittance.network_fee,
        total_fees=remittance.total_fees,
        payment_method=remittance.payment_method,
        disbursement_method=remittance.disbursement_method,
        escrow_locked_at=remittance.escrow_locked_at,
        escrow_expires_at=remittance.escrow_expires_at,
        created_at=remittance.created_at,
        updated_at=remittance.updated_at,
        completed_at=remittance.completed_at,
    )


@router.get("/reference/{reference_code}", response_model=RemittanceResponse)
async def get_remittance_by_reference(
    reference_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Obtiene detalles de una remesa por codigo de referencia.
    """
    service = RemittanceService(db)
    remittance = service.get_remittance_by_reference(reference_code)

    if not remittance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remesa no encontrada"
        )

    # Verificar acceso
    if str(remittance.sender_id) != str(current_user.id) and current_user.rol != UserRole.Admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta remesa"
        )

    return RemittanceResponse(
        id=str(remittance.id),
        reference_code=remittance.reference_code,
        status=RemittanceStatusEnum(remittance.status.value),
        recipient_info=remittance.recipient_info,
        amount_fiat_source=remittance.amount_fiat_source,
        currency_source=CurrencyEnum(remittance.currency_source.value),
        amount_fiat_destination=remittance.amount_fiat_destination,
        currency_destination=CurrencyEnum(remittance.currency_destination.value),
        amount_stablecoin=remittance.amount_stablecoin,
        stablecoin=remittance.stablecoin,
        exchange_rate_source_usd=remittance.exchange_rate_source_usd,
        platform_fee=remittance.platform_fee,
        network_fee=remittance.network_fee,
        total_fees=remittance.total_fees,
        payment_method=remittance.payment_method,
        disbursement_method=remittance.disbursement_method,
        escrow_locked_at=remittance.escrow_locked_at,
        escrow_expires_at=remittance.escrow_expires_at,
        created_at=remittance.created_at,
        updated_at=remittance.updated_at,
        completed_at=remittance.completed_at,
    )


@router.post("/{remittance_id}/lock", response_model=TransactionResponse)
async def lock_funds(
    remittance_id: str,
    request: LockFundsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Bloquea fondos en el smart contract de escrow.

    Requiere que la remesa este en estado DEPOSITED.
    """
    service = RemittanceService(db)

    # Verificar que la remesa pertenece al usuario
    remittance = service.get_remittance(remittance_id)
    if not remittance or str(remittance.sender_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remesa no encontrada"
        )

    result = await service.lock_funds_in_escrow(
        remittance_id=remittance_id,
        wallet_address=request.wallet_address,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return TransactionResponse(
        success=True,
        tx_hash=result.tx_hash,
        status=result.status.value if result.status else None,
    )


@router.post("/{remittance_id}/cancel", response_model=TransactionResponse)
async def cancel_remittance(
    remittance_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancela una remesa antes de que se procese.

    Solo disponible en estados INITIATED o PENDING_DEPOSIT.
    """
    remittance = db.query(Remittance).filter(
        Remittance.id == remittance_id,
        Remittance.sender_id == current_user.id,
    ).first()

    if not remittance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remesa no encontrada"
        )

    if remittance.status not in [RemittanceStatus.INITIATED, RemittanceStatus.PENDING_DEPOSIT]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede cancelar remesa en estado {remittance.status.value}"
        )

    remittance.status = RemittanceStatus.CANCELLED
    db.commit()

    return TransactionResponse(
        success=True,
        status="cancelled",
    )


# ============ Endpoints de Operador ============

@router.post("/{remittance_id}/release", response_model=TransactionResponse)
async def release_funds(
    remittance_id: str,
    request: ReleaseFundsRequest,
    operator: User = Depends(get_operator_user),
    db: Session = Depends(get_db),
):
    """
    Libera fondos del escrow (solo operadores).

    Se usa despues de confirmar la entrega de fondos fiat al beneficiario.
    """
    service = RemittanceService(db)

    result = await service.release_funds(
        remittance_id=remittance_id,
        operator_id=str(operator.id),
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return TransactionResponse(
        success=True,
        tx_hash=result.tx_hash,
        status=result.status.value if result.status else None,
    )


@router.get("/admin/pending-refunds", response_model=RemittanceListResponse)
async def get_pending_refunds(
    operator: User = Depends(get_operator_user),
    db: Session = Depends(get_db),
):
    """
    Lista remesas con time-lock expirado pendientes de reembolso.
    Solo para operadores.
    """
    service = RemittanceService(db)
    remittances = service.get_pending_refunds()

    return RemittanceListResponse(
        items=[
            RemittanceResponse(
                id=str(r.id),
                reference_code=r.reference_code,
                status=RemittanceStatusEnum(r.status.value),
                recipient_info=r.recipient_info,
                amount_fiat_source=r.amount_fiat_source,
                currency_source=CurrencyEnum(r.currency_source.value),
                amount_fiat_destination=r.amount_fiat_destination,
                currency_destination=CurrencyEnum(r.currency_destination.value),
                amount_stablecoin=r.amount_stablecoin,
                stablecoin=r.stablecoin,
                exchange_rate_source_usd=r.exchange_rate_source_usd,
                platform_fee=r.platform_fee,
                network_fee=r.network_fee,
                total_fees=r.total_fees,
                payment_method=r.payment_method,
                disbursement_method=r.disbursement_method,
                escrow_locked_at=r.escrow_locked_at,
                escrow_expires_at=r.escrow_expires_at,
                created_at=r.created_at,
                updated_at=r.updated_at,
                completed_at=r.completed_at,
            )
            for r in remittances
        ],
        total=len(remittances),
        page=1,
        page_size=len(remittances),
        has_more=False,
    )


@router.post("/{remittance_id}/refund", response_model=TransactionResponse)
async def process_refund(
    remittance_id: str,
    operator: User = Depends(get_operator_user),
    db: Session = Depends(get_db),
):
    """
    Procesa reembolso de una remesa expirada.
    Solo para operadores.
    """
    service = RemittanceService(db)

    result = await service.process_refund(remittance_id)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return TransactionResponse(
        success=True,
        tx_hash=result.tx_hash,
        status=result.status.value if result.status else None,
    )
