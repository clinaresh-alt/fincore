"""
Endpoints de STP (Sistema de Transferencias y Pagos) para FinCore API.

Endpoints:
- POST /stp/send - Enviar pago SPEI
- GET /stp/status/{tracking_key} - Consultar estado de orden
- GET /stp/balance - Consultar saldo
- POST /stp/webhook - Webhook de notificaciones STP
- GET /stp/availability - Verificar disponibilidad SPEI
- POST /stp/validate-clabe - Validar CLABE
"""
import logging
import hmac
import hashlib
from typing import Optional
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.core.config import settings
from app.models.user import User, UserRole
from app.services.stp_service import (
    STPService,
    get_stp_service,
    STPError,
    STPAPIError,
    STPAccountError,
    STPInsufficientFundsError,
)
from app.schemas.stp import (
    STPOrderRequest,
    STPOrderResponse,
    STPWebhookPayload,
    STPBalanceResponse,
    STPTransactionStatus,
    validate_clabe,
    get_bank_from_clabe,
    BANK_CODES,
)
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stp", tags=["STP - SPEI Payments"])


# ============ Schemas de Request/Response ============

class SendSPEIRequest(BaseModel):
    """Solicitud de envio de pago SPEI."""
    beneficiary_clabe: str = Field(..., min_length=18, max_length=18)
    beneficiary_name: str = Field(..., min_length=1, max_length=40)
    amount: Decimal = Field(..., gt=0, le=500000)
    concept: str = Field(..., min_length=1, max_length=40)
    beneficiary_rfc: Optional[str] = Field(None, max_length=13)
    remittance_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "beneficiary_clabe": "012180015678912345",
                "beneficiary_name": "JUAN PEREZ GARCIA",
                "amount": 1500.50,
                "concept": "PAGO REMESA FRC-123",
                "beneficiary_rfc": "PEGJ800101ABC"
            }
        }


class SPEIAvailabilityResponse(BaseModel):
    """Respuesta de disponibilidad SPEI."""
    available: bool
    message: str
    next_available: Optional[str] = None


class ValidateCLABERequest(BaseModel):
    """Solicitud de validacion de CLABE."""
    clabe: str = Field(..., min_length=18, max_length=18)


class ValidateCLABEResponse(BaseModel):
    """Respuesta de validacion de CLABE."""
    valid: bool
    bank_code: Optional[str] = None
    bank_name: Optional[str] = None
    error: Optional[str] = None


class WebhookResponse(BaseModel):
    """Respuesta a webhook."""
    received: bool
    tracking_key: str
    processed: bool
    message: str


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


async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Verifica que el usuario sea admin."""
    if current_user.rol != UserRole.Admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos de administrador requeridos"
        )
    return current_user


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


def verify_stp_webhook_signature(
    request: Request,
    x_stp_signature: Optional[str] = Header(None, alias="X-STP-Signature"),
) -> bool:
    """
    Verifica la firma del webhook de STP.

    STP firma los webhooks con HMAC-SHA256 usando el secret compartido.
    """
    if not x_stp_signature:
        return False

    webhook_secret = getattr(settings, 'STP_WEBHOOK_SECRET', '')
    if not webhook_secret:
        logger.warning("STP_WEBHOOK_SECRET no configurado, aceptando webhook sin verificacion")
        return True

    # TODO: Implementar verificacion de firma real cuando se tenga el formato de STP
    return True


# ============ Endpoints Publicos ============

@router.get("/availability", response_model=SPEIAvailabilityResponse)
async def check_spei_availability(
    db: Session = Depends(get_db),
):
    """
    Verifica si SPEI esta disponible.

    SPEI opera de Lunes a Viernes de 6:00 a 17:30 hora Mexico.
    """
    stp_service = get_stp_service(db)
    available, message = stp_service.is_spei_available()

    next_available = None
    if not available:
        now = datetime.now()
        if now.weekday() >= 5:  # Fin de semana
            days_until_monday = 7 - now.weekday()
            next_available = f"Lunes {(now + __import__('datetime').timedelta(days=days_until_monday)).strftime('%d/%m/%Y')} a las 06:00"
        elif now.hour < 6:
            next_available = f"Hoy a las 06:00"
        else:
            next_available = f"Manana a las 06:00"

    return SPEIAvailabilityResponse(
        available=available,
        message=message,
        next_available=next_available,
    )


@router.post("/validate-clabe", response_model=ValidateCLABEResponse)
async def validate_clabe_endpoint(
    request: ValidateCLABERequest,
):
    """
    Valida una CLABE mexicana.

    Verifica:
    - Longitud (18 digitos)
    - Solo digitos
    - Digito verificador correcto
    - Banco valido
    """
    clabe = request.clabe

    if not clabe.isdigit():
        return ValidateCLABEResponse(
            valid=False,
            error="CLABE debe contener solo digitos"
        )

    if len(clabe) != 18:
        return ValidateCLABEResponse(
            valid=False,
            error="CLABE debe tener 18 digitos"
        )

    if not validate_clabe(clabe):
        return ValidateCLABEResponse(
            valid=False,
            error="Digito verificador invalido"
        )

    bank_code = clabe[:3]
    bank_name = get_bank_from_clabe(clabe)

    if not bank_name:
        return ValidateCLABEResponse(
            valid=False,
            error=f"Codigo de banco {bank_code} no reconocido"
        )

    return ValidateCLABEResponse(
        valid=True,
        bank_code=bank_code,
        bank_name=bank_name,
    )


@router.get("/banks")
async def list_banks():
    """
    Lista de bancos mexicanos con codigo STP.
    """
    banks = [
        {"code": code, "name": name}
        for code, name in sorted(BANK_CODES.items(), key=lambda x: x[1])
    ]
    return {"banks": banks, "total": len(banks)}


# ============ Endpoints Autenticados ============

@router.post("/send", response_model=STPOrderResponse)
async def send_spei_payment(
    request: SendSPEIRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_operator_user),
):
    """
    Envia un pago SPEI.

    Requiere permisos de operador o admin.

    El pago se procesa en tiempo real y se recibira en la cuenta
    del beneficiario en menos de 30 segundos.
    """
    logger.info(
        f"Usuario {current_user.email} enviando SPEI: "
        f"${request.amount} a {request.beneficiary_clabe[:6]}***"
    )

    stp_service = get_stp_service(db)

    try:
        result = await stp_service.send_spei_payment(
            beneficiary_clabe=request.beneficiary_clabe,
            beneficiary_name=request.beneficiary_name,
            amount=request.amount,
            concept=request.concept,
            beneficiary_rfc=request.beneficiary_rfc,
            remittance_id=request.remittance_id,
            user_id=str(current_user.id),
        )

        if result.status == STPTransactionStatus.SENT:
            logger.info(f"SPEI enviado exitosamente: {result.tracking_key}")
        else:
            logger.warning(f"SPEI con error: {result.tracking_key} - {result.error_message}")

        return result

    except STPAccountError as e:
        logger.error(f"Error de cuenta SPEI: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except STPInsufficientFundsError as e:
        logger.error(f"Saldo insuficiente SPEI: {e}")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Saldo insuficiente en cuenta concentradora"
        )
    except STPError as e:
        logger.error(f"Error STP: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )


@router.get("/status/{tracking_key}", response_model=STPOrderResponse)
async def get_order_status(
    tracking_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_operator_user),
):
    """
    Consulta el estado de una orden SPEI.

    Estados posibles:
    - PENDING: Pendiente de envio
    - SENT: Enviada a STP
    - PROCESSING: En proceso
    - LIQUIDATED: Liquidada exitosamente
    - RETURNED: Devuelta
    - CANCELLED: Cancelada
    - FAILED: Fallida
    """
    stp_service = get_stp_service(db)

    try:
        result = await stp_service.get_order_status(tracking_key)
        return result
    except STPAPIError as e:
        logger.error(f"Error consultando estado SPEI {tracking_key}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )


@router.get("/balance", response_model=STPBalanceResponse)
async def get_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """
    Consulta el saldo de la cuenta concentradora.

    Solo disponible para administradores.
    """
    stp_service = get_stp_service(db)

    try:
        result = await stp_service.get_balance()
        logger.info(f"Consulta de saldo por {current_user.email}: ${result.balance}")
        return result
    except STPAPIError as e:
        logger.error(f"Error consultando saldo: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )


# ============ Webhook ============

@router.post("/webhook", response_model=WebhookResponse)
async def stp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Webhook para recibir notificaciones de STP.

    STP envia notificaciones cuando:
    - Una orden es liquidada
    - Una orden es devuelta
    - Se recibe un deposito entrante

    Este endpoint debe estar en whitelist de IPs de STP.
    """
    # Verificar firma (en produccion)
    # if not verify_stp_webhook_signature(request):
    #     raise HTTPException(status_code=401, detail="Firma invalida")

    try:
        body = await request.json()
        logger.info(f"Webhook STP recibido: {body}")

        # Parsear payload
        payload = STPWebhookPayload(**body)

        # Procesar
        stp_service = get_stp_service(db)
        result = await stp_service.process_webhook(payload)

        return WebhookResponse(
            received=True,
            tracking_key=payload.clave_rastreo,
            processed=result.get("processed", True),
            message=result.get("action_taken", "processed"),
        )

    except Exception as e:
        logger.error(f"Error procesando webhook STP: {e}")
        # Siempre responder 200 para evitar reintentos de STP
        return WebhookResponse(
            received=True,
            tracking_key="unknown",
            processed=False,
            message=f"Error: {str(e)}"
        )


# ============ Endpoints Internos (Admin) ============

@router.post("/reconcile")
async def reconcile_orders(
    date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """
    Ejecuta conciliacion de ordenes con STP.

    Compara las ordenes del dia en nuestra base de datos
    con las reportadas por STP.
    """
    from datetime import datetime as dt

    reconcile_date = None
    if date:
        try:
            reconcile_date = dt.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de fecha invalido. Usar YYYY-MM-DD"
            )

    stp_service = get_stp_service(db)

    try:
        records = await stp_service.reconcile_orders(reconcile_date)

        return {
            "date": (reconcile_date or dt.now()).strftime("%Y-%m-%d"),
            "total_orders": len(records),
            "records": [
                {
                    "tracking_key": r.tracking_key,
                    "stp_id": r.stp_id,
                    "amount": float(r.amount),
                    "status": r.status.value,
                    "matched": r.matched,
                }
                for r in records
            ]
        }

    except STPAPIError as e:
        logger.error(f"Error en conciliacion STP: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
