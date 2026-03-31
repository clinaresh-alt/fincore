"""
Endpoints para Fincore Pay - Pagos P2P y QR.
Sistema de pagos instantáneos entre usuarios.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID
from decimal import Decimal

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.fincore_pay import (
    P2PTransfer, PaymentRequest, QRPayment, QRTransaction, ContactPayment,
    P2PTransferStatus, PaymentRequestStatus, QRPaymentType
)
from app.schemas.fincore_pay import (
    P2PTransferCreate, P2PTransferResponse, P2PTransferList, P2PTransferCancel,
    PaymentRequestCreate, PaymentRequestResponse, PaymentRequestList, PaymentRequestPay,
    QRPaymentCreate, QRPaymentResponse, QRPaymentList, QRPaymentScan, QRPaymentScanResponse,
    QRPaymentExecute, QRTransactionResponse,
    ContactPaymentCreate, ContactPaymentUpdate, ContactPaymentResponse, ContactPaymentList,
    PayAnalytics, PayLimits
)
from app.infrastructure import get_logger

router = APIRouter(prefix="/pay", tags=["Fincore Pay"])
logger = get_logger(__name__)


# =====================
# P2P Transfers
# =====================

@router.post("/transfer", response_model=P2PTransferResponse, status_code=status.HTTP_201_CREATED)
async def create_p2p_transfer(
    transfer: P2PTransferCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Crear transferencia P2P a otro usuario.

    Identificadores soportados:
    - phone: Número de teléfono
    - email: Correo electrónico
    - username: Nombre de usuario
    - wallet: Dirección de wallet
    """
    # Buscar receptor
    receiver_query = select(User)

    if transfer.receiver_identifier_type.value == "phone":
        receiver_query = receiver_query.where(User.phone == transfer.receiver_identifier)
    elif transfer.receiver_identifier_type.value == "email":
        receiver_query = receiver_query.where(User.email == transfer.receiver_identifier)
    elif transfer.receiver_identifier_type.value == "username":
        receiver_query = receiver_query.where(User.username == transfer.receiver_identifier)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de identificador no soportado para P2P"
        )

    result = await db.execute(receiver_query)
    receiver = result.scalar_one_or_none()

    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario receptor no encontrado"
        )

    if receiver.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes transferirte a ti mismo"
        )

    # Validar balance del usuario (implementación simplificada)
    # En producción, esto consultaría el balance real

    # Calcular fee (0% para P2P interno)
    fee = Decimal("0")

    # Crear transferencia
    p2p_transfer = P2PTransfer(
        transfer_number=P2PTransfer.generate_transfer_number(),
        sender_id=current_user.id,
        receiver_id=receiver.id,
        amount=transfer.amount,
        currency=transfer.currency,
        fee=fee,
        status=P2PTransferStatus.PROCESSING,
        receiver_identifier_type=transfer.receiver_identifier_type.value,
        receiver_identifier=transfer.receiver_identifier,
        concept=transfer.concept,
        note=transfer.note,
        reference_id=transfer.reference_id
    )

    db.add(p2p_transfer)
    await db.commit()
    await db.refresh(p2p_transfer)

    # Procesar transferencia en background
    # background_tasks.add_task(process_p2p_transfer, p2p_transfer.id)

    # Marcar como completada inmediatamente para demo
    p2p_transfer.status = P2PTransferStatus.COMPLETED
    p2p_transfer.processed_at = datetime.utcnow()
    p2p_transfer.completed_at = datetime.utcnow()
    await db.commit()

    logger.info(
        "P2P transfer created",
        extra={
            "transfer_id": str(p2p_transfer.id),
            "sender_id": str(current_user.id),
            "receiver_id": str(receiver.id),
            "amount": str(transfer.amount)
        }
    )

    return P2PTransferResponse(
        **{k: v for k, v in p2p_transfer.__dict__.items() if not k.startswith("_")},
        receiver_name=f"{receiver.nombre} {receiver.apellido}",
        receiver_avatar=None
    )


@router.get("/transfers", response_model=P2PTransferList)
async def list_p2p_transfers(
    direction: Optional[str] = Query(None, regex="^(sent|received|all)$"),
    status_filter: Optional[P2PTransferStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar transferencias P2P del usuario."""
    query = select(P2PTransfer)

    if direction == "sent":
        query = query.where(P2PTransfer.sender_id == current_user.id)
    elif direction == "received":
        query = query.where(P2PTransfer.receiver_id == current_user.id)
    else:
        query = query.where(
            or_(
                P2PTransfer.sender_id == current_user.id,
                P2PTransfer.receiver_id == current_user.id
            )
        )

    if status_filter:
        query = query.where(P2PTransfer.status == status_filter)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(P2PTransfer.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    transfers = result.scalars().all()

    return P2PTransferList(
        transfers=[
            P2PTransferResponse(**{k: v for k, v in t.__dict__.items() if not k.startswith("_")})
            for t in transfers
        ],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/transfer/{transfer_id}", response_model=P2PTransferResponse)
async def get_p2p_transfer(
    transfer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener detalle de transferencia P2P."""
    query = select(P2PTransfer).where(
        P2PTransfer.id == transfer_id,
        or_(
            P2PTransfer.sender_id == current_user.id,
            P2PTransfer.receiver_id == current_user.id
        )
    )

    result = await db.execute(query)
    transfer = result.scalar_one_or_none()

    if not transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transferencia no encontrada"
        )

    return P2PTransferResponse(**{k: v for k, v in transfer.__dict__.items() if not k.startswith("_")})


@router.post("/transfer/{transfer_id}/cancel", response_model=P2PTransferResponse)
async def cancel_p2p_transfer(
    transfer_id: UUID,
    cancel_data: P2PTransferCancel,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Cancelar transferencia P2P pendiente."""
    query = select(P2PTransfer).where(
        P2PTransfer.id == transfer_id,
        P2PTransfer.sender_id == current_user.id,
        P2PTransfer.status == P2PTransferStatus.PENDING
    )

    result = await db.execute(query)
    transfer = result.scalar_one_or_none()

    if not transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transferencia no encontrada o no cancelable"
        )

    transfer.status = P2PTransferStatus.CANCELLED
    transfer.metadata = {**transfer.metadata, "cancel_reason": cancel_data.reason}

    await db.commit()
    await db.refresh(transfer)

    return P2PTransferResponse(**{k: v for k, v in transfer.__dict__.items() if not k.startswith("_")})


# =====================
# Payment Requests
# =====================

@router.post("/request", response_model=PaymentRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_payment_request(
    request_data: PaymentRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Crear solicitud de pago."""
    payer_id = None

    if request_data.payer_identifier and request_data.payer_identifier_type:
        # Buscar pagador específico
        payer_query = select(User)

        if request_data.payer_identifier_type.value == "phone":
            payer_query = payer_query.where(User.phone == request_data.payer_identifier)
        elif request_data.payer_identifier_type.value == "email":
            payer_query = payer_query.where(User.email == request_data.payer_identifier)

        result = await db.execute(payer_query)
        payer = result.scalar_one_or_none()

        if payer:
            payer_id = payer.id

    expires_at = None
    if request_data.expires_in_hours:
        expires_at = datetime.utcnow() + timedelta(hours=request_data.expires_in_hours)

    payment_request = PaymentRequest(
        request_code=PaymentRequest.generate_request_code(),
        requester_id=current_user.id,
        payer_id=payer_id,
        amount=request_data.amount,
        currency=request_data.currency,
        description=request_data.description,
        note=request_data.note,
        status=PaymentRequestStatus.PENDING,
        expires_at=expires_at
    )

    db.add(payment_request)
    await db.commit()
    await db.refresh(payment_request)

    return PaymentRequestResponse(
        **{k: v for k, v in payment_request.__dict__.items() if not k.startswith("_")},
        requester_name=f"{current_user.nombre} {current_user.apellido}",
        payment_link=f"https://pay.fincore.com/r/{payment_request.request_code}"
    )


@router.get("/requests", response_model=PaymentRequestList)
async def list_payment_requests(
    direction: Optional[str] = Query("created", regex="^(created|received|all)$"),
    status_filter: Optional[PaymentRequestStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar solicitudes de pago."""
    query = select(PaymentRequest)

    if direction == "created":
        query = query.where(PaymentRequest.requester_id == current_user.id)
    elif direction == "received":
        query = query.where(PaymentRequest.payer_id == current_user.id)
    else:
        query = query.where(
            or_(
                PaymentRequest.requester_id == current_user.id,
                PaymentRequest.payer_id == current_user.id
            )
        )

    if status_filter:
        query = query.where(PaymentRequest.status == status_filter)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(PaymentRequest.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    requests = result.scalars().all()

    return PaymentRequestList(
        requests=[
            PaymentRequestResponse(**{k: v for k, v in r.__dict__.items() if not k.startswith("_")})
            for r in requests
        ],
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/request/{request_code}/pay", response_model=P2PTransferResponse)
async def pay_payment_request(
    request_code: str,
    pay_data: PaymentRequestPay,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Pagar una solicitud de pago."""
    query = select(PaymentRequest).where(
        PaymentRequest.request_code == request_code,
        PaymentRequest.status == PaymentRequestStatus.PENDING
    )

    result = await db.execute(query)
    payment_request = result.scalar_one_or_none()

    if not payment_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud de pago no encontrada o ya pagada"
        )

    if payment_request.expires_at and datetime.utcnow() > payment_request.expires_at:
        payment_request.status = PaymentRequestStatus.EXPIRED
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solicitud de pago expirada"
        )

    if payment_request.requester_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes pagar tu propia solicitud"
        )

    # Crear transferencia P2P
    p2p_transfer = P2PTransfer(
        transfer_number=P2PTransfer.generate_transfer_number(),
        sender_id=current_user.id,
        receiver_id=payment_request.requester_id,
        amount=payment_request.amount,
        currency=payment_request.currency,
        fee=Decimal("0"),
        status=P2PTransferStatus.COMPLETED,
        concept=payment_request.description,
        note=pay_data.note,
        payment_request_id=payment_request.id,
        processed_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )

    db.add(p2p_transfer)

    # Actualizar solicitud
    payment_request.status = PaymentRequestStatus.PAID
    payment_request.transfer_id = p2p_transfer.id
    payment_request.paid_at = datetime.utcnow()

    await db.commit()
    await db.refresh(p2p_transfer)

    return P2PTransferResponse(**{k: v for k, v in p2p_transfer.__dict__.items() if not k.startswith("_")})


@router.post("/request/{request_id}/cancel")
async def cancel_payment_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Cancelar solicitud de pago propia."""
    query = select(PaymentRequest).where(
        PaymentRequest.id == request_id,
        PaymentRequest.requester_id == current_user.id,
        PaymentRequest.status == PaymentRequestStatus.PENDING
    )

    result = await db.execute(query)
    payment_request = result.scalar_one_or_none()

    if not payment_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud no encontrada o no cancelable"
        )

    payment_request.status = PaymentRequestStatus.CANCELLED
    await db.commit()

    return {"message": "Solicitud cancelada"}


# =====================
# QR Payments
# =====================

@router.post("/qr", response_model=QRPaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_qr_payment(
    qr_data: QRPaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Crear código QR para recibir pagos."""
    expires_at = None
    if qr_data.expires_in_minutes:
        expires_at = datetime.utcnow() + timedelta(minutes=qr_data.expires_in_minutes)

    qr_payment = QRPayment(
        qr_code=QRPayment.generate_qr_code(),
        owner_id=current_user.id,
        qr_type=qr_data.qr_type,
        amount=qr_data.amount,
        currency=qr_data.currency,
        description=qr_data.description,
        merchant_name=qr_data.merchant_name or f"{current_user.nombre} {current_user.apellido}",
        merchant_category=qr_data.merchant_category,
        min_amount=qr_data.min_amount,
        max_amount=qr_data.max_amount,
        max_uses=qr_data.max_uses,
        expires_at=expires_at,
        is_active=True
    )

    db.add(qr_payment)
    await db.commit()
    await db.refresh(qr_payment)

    # Generar imagen QR
    qr_image = qr_payment.generate_qr_image()

    return QRPaymentResponse(
        **{k: v for k, v in qr_payment.__dict__.items() if not k.startswith("_")},
        qr_image_base64=qr_image,
        payment_url=f"https://pay.fincore.com/qr/{qr_payment.qr_code}"
    )


@router.get("/qr", response_model=QRPaymentList)
async def list_qr_payments(
    active_only: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar códigos QR del usuario."""
    query = select(QRPayment).where(QRPayment.owner_id == current_user.id)

    if active_only:
        query = query.where(QRPayment.is_active == True)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(QRPayment.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    qr_codes = result.scalars().all()

    return QRPaymentList(
        qr_codes=[
            QRPaymentResponse(**{k: v for k, v in qr.__dict__.items() if not k.startswith("_")})
            for qr in qr_codes
        ],
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/qr/scan", response_model=QRPaymentScanResponse)
async def scan_qr_payment(
    scan_data: QRPaymentScan,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Escanear código QR para ver detalles antes de pagar."""
    query = select(QRPayment).where(
        QRPayment.qr_code == scan_data.qr_code,
        QRPayment.is_active == True
    )

    result = await db.execute(query)
    qr_payment = result.scalar_one_or_none()

    if not qr_payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Código QR no encontrado o inactivo"
        )

    # Validaciones
    can_pay = True
    reason = None

    if qr_payment.owner_id == current_user.id:
        can_pay = False
        reason = "No puedes pagar tu propio QR"
    elif qr_payment.expires_at and datetime.utcnow() > qr_payment.expires_at:
        can_pay = False
        reason = "Código QR expirado"
    elif qr_payment.qr_type == QRPaymentType.ONE_TIME and qr_payment.is_used:
        can_pay = False
        reason = "Código QR de un solo uso ya utilizado"
    elif qr_payment.max_uses and qr_payment.use_count >= qr_payment.max_uses:
        can_pay = False
        reason = "Código QR alcanzó el máximo de usos"

    # Obtener info del propietario
    owner_query = select(User).where(User.id == qr_payment.owner_id)
    owner_result = await db.execute(owner_query)
    owner = owner_result.scalar_one()

    return QRPaymentScanResponse(
        qr_payment=QRPaymentResponse(**{k: v for k, v in qr_payment.__dict__.items() if not k.startswith("_")}),
        owner_name=f"{owner.nombre} {owner.apellido}",
        owner_avatar=None,
        can_pay=can_pay,
        reason=reason
    )


@router.post("/qr/pay", response_model=P2PTransferResponse)
async def execute_qr_payment(
    execute_data: QRPaymentExecute,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Ejecutar pago mediante código QR."""
    query = select(QRPayment).where(
        QRPayment.qr_code == execute_data.qr_code,
        QRPayment.is_active == True
    )

    result = await db.execute(query)
    qr_payment = result.scalar_one_or_none()

    if not qr_payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Código QR no encontrado o inactivo"
        )

    # Validaciones
    if qr_payment.owner_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes pagar tu propio QR"
        )

    if qr_payment.expires_at and datetime.utcnow() > qr_payment.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código QR expirado"
        )

    # Determinar monto
    amount = execute_data.amount or qr_payment.amount

    if qr_payment.qr_type == QRPaymentType.DYNAMIC and not qr_payment.amount:
        if not execute_data.amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere monto para este QR"
            )

    if qr_payment.qr_type != QRPaymentType.STATIC and qr_payment.amount:
        amount = qr_payment.amount

    if qr_payment.min_amount and amount < qr_payment.min_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Monto mínimo: {qr_payment.min_amount}"
        )

    if qr_payment.max_amount and amount > qr_payment.max_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Monto máximo: {qr_payment.max_amount}"
        )

    # Crear transferencia P2P
    p2p_transfer = P2PTransfer(
        transfer_number=P2PTransfer.generate_transfer_number(),
        sender_id=current_user.id,
        receiver_id=qr_payment.owner_id,
        amount=amount,
        currency=qr_payment.currency,
        fee=Decimal("0"),
        status=P2PTransferStatus.COMPLETED,
        concept=qr_payment.description or "Pago QR",
        note=execute_data.note,
        processed_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )

    db.add(p2p_transfer)

    # Crear registro de transacción QR
    qr_transaction = QRTransaction(
        qr_payment_id=qr_payment.id,
        payer_id=current_user.id,
        p2p_transfer_id=p2p_transfer.id,
        amount=amount,
        currency=qr_payment.currency
    )

    db.add(qr_transaction)

    # Actualizar QR
    qr_payment.use_count += 1
    qr_payment.last_used_at = datetime.utcnow()

    if qr_payment.qr_type == QRPaymentType.ONE_TIME:
        qr_payment.is_used = True
        qr_payment.is_active = False

    await db.commit()
    await db.refresh(p2p_transfer)

    return P2PTransferResponse(**{k: v for k, v in p2p_transfer.__dict__.items() if not k.startswith("_")})


@router.delete("/qr/{qr_id}")
async def deactivate_qr_payment(
    qr_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Desactivar código QR."""
    query = select(QRPayment).where(
        QRPayment.id == qr_id,
        QRPayment.owner_id == current_user.id
    )

    result = await db.execute(query)
    qr_payment = result.scalar_one_or_none()

    if not qr_payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Código QR no encontrado"
        )

    qr_payment.is_active = False
    await db.commit()

    return {"message": "Código QR desactivado"}


# =====================
# Contacts
# =====================

@router.post("/contacts", response_model=ContactPaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    contact_data: ContactPaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Agregar contacto de pago."""
    # Buscar si es usuario de la plataforma
    contact_user_id = None
    contact_query = select(User)

    if contact_data.contact_identifier_type.value == "phone":
        contact_query = contact_query.where(User.phone == contact_data.contact_identifier)
    elif contact_data.contact_identifier_type.value == "email":
        contact_query = contact_query.where(User.email == contact_data.contact_identifier)

    result = await db.execute(contact_query)
    contact_user = result.scalar_one_or_none()

    if contact_user:
        contact_user_id = contact_user.id

    contact = ContactPayment(
        user_id=current_user.id,
        contact_user_id=contact_user_id,
        contact_name=contact_data.contact_name,
        contact_identifier_type=contact_data.contact_identifier_type.value,
        contact_identifier=contact_data.contact_identifier,
        alias=contact_data.alias,
        is_favorite=contact_data.is_favorite
    )

    db.add(contact)
    await db.commit()
    await db.refresh(contact)

    return ContactPaymentResponse(
        **{k: v for k, v in contact.__dict__.items() if not k.startswith("_")},
        is_platform_user=contact_user_id is not None
    )


@router.get("/contacts", response_model=ContactPaymentList)
async def list_contacts(
    favorites_only: bool = False,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Listar contactos de pago."""
    query = select(ContactPayment).where(
        ContactPayment.user_id == current_user.id,
        ContactPayment.is_active == True
    )

    if favorites_only:
        query = query.where(ContactPayment.is_favorite == True)

    if search:
        query = query.where(
            or_(
                ContactPayment.contact_name.ilike(f"%{search}%"),
                ContactPayment.alias.ilike(f"%{search}%"),
                ContactPayment.contact_identifier.ilike(f"%{search}%")
            )
        )

    query = query.order_by(
        ContactPayment.is_favorite.desc(),
        ContactPayment.payment_count.desc()
    )

    result = await db.execute(query)
    contacts = result.scalars().all()

    favorites_count = len([c for c in contacts if c.is_favorite])

    return ContactPaymentList(
        contacts=[
            ContactPaymentResponse(
                **{k: v for k, v in c.__dict__.items() if not k.startswith("_")},
                is_platform_user=c.contact_user_id is not None
            )
            for c in contacts
        ],
        total=len(contacts),
        favorites=favorites_count
    )


@router.patch("/contacts/{contact_id}", response_model=ContactPaymentResponse)
async def update_contact(
    contact_id: UUID,
    update_data: ContactPaymentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Actualizar contacto de pago."""
    query = select(ContactPayment).where(
        ContactPayment.id == contact_id,
        ContactPayment.user_id == current_user.id
    )

    result = await db.execute(query)
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contacto no encontrado"
        )

    update_dict = update_data.dict(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(contact, key, value)

    await db.commit()
    await db.refresh(contact)

    return ContactPaymentResponse(
        **{k: v for k, v in contact.__dict__.items() if not k.startswith("_")},
        is_platform_user=contact.contact_user_id is not None
    )


@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Eliminar contacto de pago."""
    query = select(ContactPayment).where(
        ContactPayment.id == contact_id,
        ContactPayment.user_id == current_user.id
    )

    result = await db.execute(query)
    contact = result.scalar_one_or_none()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contacto no encontrado"
        )

    contact.is_active = False
    await db.commit()

    return {"message": "Contacto eliminado"}


# =====================
# Analytics
# =====================

@router.get("/analytics", response_model=PayAnalytics)
async def get_pay_analytics(
    period: str = Query("month", regex="^(week|month|year|all)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener analíticas de pagos."""
    # Calcular fecha de inicio según período
    now = datetime.utcnow()
    if period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    elif period == "year":
        start_date = now - timedelta(days=365)
    else:
        start_date = datetime(2020, 1, 1)

    # Sent
    sent_query = select(
        func.sum(P2PTransfer.amount),
        func.count(P2PTransfer.id)
    ).where(
        P2PTransfer.sender_id == current_user.id,
        P2PTransfer.status == P2PTransferStatus.COMPLETED,
        P2PTransfer.created_at >= start_date
    )
    sent_result = await db.execute(sent_query)
    sent_data = sent_result.one()
    total_sent = sent_data[0] or Decimal("0")
    transactions_sent = sent_data[1] or 0

    # Received
    received_query = select(
        func.sum(P2PTransfer.amount),
        func.count(P2PTransfer.id)
    ).where(
        P2PTransfer.receiver_id == current_user.id,
        P2PTransfer.status == P2PTransferStatus.COMPLETED,
        P2PTransfer.created_at >= start_date
    )
    received_result = await db.execute(received_query)
    received_data = received_result.one()
    total_received = received_data[0] or Decimal("0")
    transactions_received = received_data[1] or 0

    return PayAnalytics(
        total_sent=total_sent,
        total_received=total_received,
        total_transactions=transactions_sent + transactions_received,
        transactions_sent=transactions_sent,
        transactions_received=transactions_received,
        average_sent=total_sent / max(transactions_sent, 1),
        average_received=total_received / max(transactions_received, 1),
        most_paid_contacts=[],
        transactions_by_day=[],
        transactions_by_hour=[]
    )


@router.get("/limits", response_model=PayLimits)
async def get_pay_limits(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener límites de pago del usuario."""
    # Límites base (en producción vendrían del perfil del usuario)
    daily_limit = Decimal("100000")
    monthly_limit = Decimal("500000")
    single_limit = Decimal("50000")
    contacts_limit = 100

    # Calcular uso diario
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_query = select(func.sum(P2PTransfer.amount)).where(
        P2PTransfer.sender_id == current_user.id,
        P2PTransfer.status == P2PTransferStatus.COMPLETED,
        P2PTransfer.created_at >= today
    )
    daily_result = await db.execute(daily_query)
    daily_used = daily_result.scalar() or Decimal("0")

    # Calcular uso mensual
    month_start = today.replace(day=1)
    monthly_query = select(func.sum(P2PTransfer.amount)).where(
        P2PTransfer.sender_id == current_user.id,
        P2PTransfer.status == P2PTransferStatus.COMPLETED,
        P2PTransfer.created_at >= month_start
    )
    monthly_result = await db.execute(monthly_query)
    monthly_used = monthly_result.scalar() or Decimal("0")

    # Contar contactos
    contacts_query = select(func.count(ContactPayment.id)).where(
        ContactPayment.user_id == current_user.id,
        ContactPayment.is_active == True
    )
    contacts_result = await db.execute(contacts_query)
    contacts_used = contacts_result.scalar() or 0

    return PayLimits(
        daily_limit=daily_limit,
        daily_used=daily_used,
        daily_remaining=max(daily_limit - daily_used, Decimal("0")),
        monthly_limit=monthly_limit,
        monthly_used=monthly_used,
        monthly_remaining=max(monthly_limit - monthly_used, Decimal("0")),
        single_transaction_limit=single_limit,
        contacts_limit=contacts_limit,
        contacts_used=contacts_used
    )
