"""
API Endpoints para recibir webhooks de STP y Bitso.

Estos endpoints son llamados por servicios externos cuando
ocurren eventos relevantes (pagos liquidados, órdenes completadas, etc.)
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.webhook_service import (
    get_inbound_webhook_processor,
    InboundWebhookProcessor,
)
from app.schemas.webhooks import (
    WebhookLogEntry,
    WebhookSource,
    WebhookEventType,
)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


# ============ Response Models ============

class WebhookResponse(BaseModel):
    """Respuesta estándar para webhooks."""
    success: bool
    message: str
    event_id: Optional[str] = None
    processed_at: datetime


class WebhookAckResponse(BaseModel):
    """Respuesta de acknowledgment simple."""
    received: bool = True


# ============ STP Webhook Endpoints ============

@router.post("/stp", response_model=WebhookResponse)
async def receive_stp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_stp_signature: Optional[str] = Header(None, alias="X-STP-Signature"),
):
    """
    Recibe webhooks de STP.

    STP envía notificaciones cuando:
    - Un pago SPEI es liquidado
    - Un pago es devuelto
    - Se recibe un depósito

    Headers esperados:
    - X-STP-Signature: Firma HMAC-SHA256 del payload
    """
    try:
        # Leer body raw para verificación de firma
        body = await request.body()

        # Obtener procesador
        processor = get_inbound_webhook_processor(db)

        # Procesar webhook
        result = await processor.process_stp_webhook(
            payload=body,
            signature=x_stp_signature,
        )

        return WebhookResponse(
            success=result.get("success", True),
            message=result.get("message", "Webhook procesado"),
            event_id=result.get("event_id"),
            processed_at=datetime.utcnow(),
        )

    except ValueError as e:
        # Error de validación (firma inválida, payload malformado)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Error interno - aún así responder 200 para evitar reintentos
        # pero loggear el error
        return WebhookResponse(
            success=False,
            message=f"Error procesando webhook: {str(e)}",
            processed_at=datetime.utcnow(),
        )


@router.post("/stp/ack", response_model=WebhookAckResponse)
async def ack_stp_webhook(request: Request):
    """
    Endpoint simple de acknowledgment para STP.

    Algunos sistemas esperan una respuesta rápida sin procesamiento.
    El procesamiento real se hace de forma asíncrona.
    """
    # Solo confirmar recepción
    return WebhookAckResponse(received=True)


# ============ Bitso Webhook Endpoints ============

@router.post("/bitso", response_model=WebhookResponse)
async def receive_bitso_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_bitso_signature: Optional[str] = Header(None, alias="X-Bitso-Signature"),
):
    """
    Recibe webhooks de Bitso.

    Bitso envía notificaciones para:
    - Órdenes completadas/canceladas
    - Retiros procesados
    - Depósitos recibidos

    Headers esperados:
    - X-Bitso-Signature: Firma HMAC-SHA256 del payload
    """
    try:
        # Leer body raw para verificación de firma
        body = await request.body()

        # Obtener procesador
        processor = get_inbound_webhook_processor(db)

        # Procesar webhook
        result = await processor.process_bitso_webhook(
            payload=body,
            signature=x_bitso_signature,
        )

        return WebhookResponse(
            success=result.get("success", True),
            message=result.get("message", "Webhook procesado"),
            event_id=result.get("event_id"),
            processed_at=datetime.utcnow(),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return WebhookResponse(
            success=False,
            message=f"Error procesando webhook: {str(e)}",
            processed_at=datetime.utcnow(),
        )


# ============ Generic Webhook Endpoint ============

@router.post("/receive/{source}", response_model=WebhookResponse)
async def receive_generic_webhook(
    source: str,
    request: Request,
    db: Session = Depends(get_db),
    x_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
):
    """
    Endpoint genérico para webhooks.

    Permite recibir webhooks de cualquier fuente configurada.
    El source debe ser: stp, bitso, blockchain, internal
    """
    valid_sources = ["stp", "bitso", "blockchain", "internal"]

    if source not in valid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Source inválido. Debe ser uno de: {valid_sources}"
        )

    try:
        body = await request.body()
        processor = get_inbound_webhook_processor(db)

        if source == "stp":
            result = await processor.process_stp_webhook(body, x_signature)
        elif source == "bitso":
            result = await processor.process_bitso_webhook(body, x_signature)
        else:
            # Para blockchain/internal, usar procesamiento genérico
            result = {
                "success": True,
                "message": f"Webhook de {source} recibido",
                "event_id": None,
            }

        return WebhookResponse(
            success=result.get("success", True),
            message=result.get("message", "Webhook procesado"),
            event_id=result.get("event_id"),
            processed_at=datetime.utcnow(),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return WebhookResponse(
            success=False,
            message=f"Error: {str(e)}",
            processed_at=datetime.utcnow(),
        )


# ============ Webhook Status Endpoints ============

@router.get("/status")
async def get_webhook_status():
    """
    Verifica el estado del sistema de webhooks.

    Útil para health checks de los servicios externos.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "stp": "/api/v1/webhooks/stp",
            "bitso": "/api/v1/webhooks/bitso",
        },
        "version": "1.0.0",
    }


@router.get("/test")
async def test_webhook_endpoint():
    """
    Endpoint de prueba para verificar conectividad.

    Los servicios externos pueden usar este endpoint
    para verificar que pueden alcanzar nuestro servidor.
    """
    return {
        "message": "Webhook endpoint activo",
        "timestamp": datetime.utcnow().isoformat(),
    }
