"""
Schemas para sistema de Webhooks bidireccionales.

Define modelos para:
- Webhooks entrantes (STP, Bitso)
- Webhooks salientes (notificaciones a clientes)
- Registro y auditoria de webhooks
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, HttpUrl
from enum import Enum
import hashlib
import hmac
import json


# ============ Enums ============

class WebhookSource(str, Enum):
    """Origen del webhook."""
    STP = "stp"
    BITSO = "bitso"
    BLOCKCHAIN = "blockchain"
    INTERNAL = "internal"


class WebhookEventType(str, Enum):
    """Tipos de eventos de webhook."""
    # STP Events
    STP_PAYMENT_SENT = "stp.payment.sent"
    STP_PAYMENT_LIQUIDATED = "stp.payment.liquidated"
    STP_PAYMENT_RETURNED = "stp.payment.returned"
    STP_PAYMENT_CANCELLED = "stp.payment.cancelled"
    STP_DEPOSIT_RECEIVED = "stp.deposit.received"

    # Bitso Events
    BITSO_ORDER_COMPLETED = "bitso.order.completed"
    BITSO_ORDER_CANCELLED = "bitso.order.cancelled"
    BITSO_WITHDRAWAL_PENDING = "bitso.withdrawal.pending"
    BITSO_WITHDRAWAL_COMPLETE = "bitso.withdrawal.complete"
    BITSO_WITHDRAWAL_FAILED = "bitso.withdrawal.failed"
    BITSO_DEPOSIT_RECEIVED = "bitso.deposit.received"

    # Remittance Events
    REMITTANCE_CREATED = "remittance.created"
    REMITTANCE_DEPOSITED = "remittance.deposited"
    REMITTANCE_LOCKED = "remittance.locked"
    REMITTANCE_CONVERTING = "remittance.converting"
    REMITTANCE_DISBURSING = "remittance.disbursing"
    REMITTANCE_COMPLETED = "remittance.completed"
    REMITTANCE_FAILED = "remittance.failed"
    REMITTANCE_REFUNDED = "remittance.refunded"

    # Compliance Events
    COMPLIANCE_SCREENING_COMPLETED = "compliance.screening.completed"
    COMPLIANCE_ALERT = "compliance.alert"


class WebhookStatus(str, Enum):
    """Estado de entrega de webhook."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookDeliveryStatus(str, Enum):
    """Estado detallado de intento de entrega."""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    HTTP_ERROR = "http_error"
    INVALID_RESPONSE = "invalid_response"


# ============ Incoming Webhooks (from STP/Bitso) ============

class STPWebhookEvent(BaseModel):
    """
    Webhook recibido de STP.

    STP envia notificaciones cuando:
    - Un pago SPEI es liquidado
    - Un pago es devuelto
    - Se recibe un deposito
    """
    id: int = Field(..., description="ID de la operacion en STP")
    claveRastreo: str = Field(..., description="Clave de rastreo SPEI")
    tipoOperacion: int = Field(..., description="1=Envio, 2=Recepcion")
    estado: int = Field(..., description="0=Liquidado, 2=Devuelto, etc.")
    monto: int = Field(..., description="Monto en centavos")
    cuentaOrdenante: Optional[str] = None
    nombreOrdenante: Optional[str] = None
    cuentaBeneficiario: Optional[str] = None
    nombreBeneficiario: Optional[str] = None
    concepto: Optional[str] = None
    referenciaNumerica: Optional[int] = None
    fechaOperacion: Optional[int] = None  # YYYYMMDD
    horaOperacion: Optional[str] = None
    causaDevolucion: Optional[int] = None
    rfcCurpBeneficiario: Optional[str] = None

    @property
    def amount_decimal(self) -> Decimal:
        """Convierte centavos a pesos."""
        return Decimal(self.monto) / 100

    @property
    def is_liquidated(self) -> bool:
        return self.estado == 0

    @property
    def is_returned(self) -> bool:
        return self.estado == 2

    @property
    def is_cancelled(self) -> bool:
        return self.estado == 3

    @property
    def event_type(self) -> WebhookEventType:
        """Determina el tipo de evento."""
        if self.tipoOperacion == 2:
            return WebhookEventType.STP_DEPOSIT_RECEIVED

        if self.is_liquidated:
            return WebhookEventType.STP_PAYMENT_LIQUIDATED
        elif self.is_returned:
            return WebhookEventType.STP_PAYMENT_RETURNED
        elif self.is_cancelled:
            return WebhookEventType.STP_PAYMENT_CANCELLED
        else:
            return WebhookEventType.STP_PAYMENT_SENT


class BitsoWebhookEvent(BaseModel):
    """
    Webhook recibido de Bitso.

    Bitso envia notificaciones para:
    - Ordenes completadas/canceladas
    - Retiros procesados
    - Depositos recibidos
    """
    type: str = Field(..., description="Tipo de evento")
    payload: Dict[str, Any] = Field(..., description="Datos del evento")
    created_at: datetime

    @property
    def event_type(self) -> WebhookEventType:
        """Mapea tipo de Bitso a nuestro enum."""
        type_map = {
            "order.completed": WebhookEventType.BITSO_ORDER_COMPLETED,
            "order.cancelled": WebhookEventType.BITSO_ORDER_CANCELLED,
            "withdrawal.pending": WebhookEventType.BITSO_WITHDRAWAL_PENDING,
            "withdrawal.complete": WebhookEventType.BITSO_WITHDRAWAL_COMPLETE,
            "withdrawal.failed": WebhookEventType.BITSO_WITHDRAWAL_FAILED,
            "funding.complete": WebhookEventType.BITSO_DEPOSIT_RECEIVED,
        }
        return type_map.get(self.type, WebhookEventType.BITSO_ORDER_COMPLETED)

    @property
    def order_id(self) -> Optional[str]:
        return self.payload.get("oid")

    @property
    def withdrawal_id(self) -> Optional[str]:
        return self.payload.get("wid")

    @property
    def funding_id(self) -> Optional[str]:
        return self.payload.get("fid")


# ============ Outgoing Webhooks (to clients) ============

class WebhookEndpoint(BaseModel):
    """Configuracion de endpoint de webhook de un cliente."""
    id: str
    user_id: str
    url: str = Field(..., description="URL de destino")
    secret: str = Field(..., description="Secret para firma HMAC")
    events: List[WebhookEventType] = Field(
        default_factory=list,
        description="Eventos suscritos (vacio = todos)"
    )
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Configuracion de reintentos
    max_retries: int = 5
    retry_delay_seconds: int = 60

    # Headers personalizados
    custom_headers: Dict[str, str] = Field(default_factory=dict)


class WebhookPayload(BaseModel):
    """Payload de webhook saliente."""
    id: str = Field(..., description="ID unico del webhook")
    event: WebhookEventType
    created_at: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any]

    # Referencias
    remittance_id: Optional[str] = None
    user_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event": self.event.value,
            "created_at": self.created_at.isoformat(),
            "data": self.data,
            "remittance_id": self.remittance_id,
            "user_id": self.user_id,
        }

    def sign(self, secret: str) -> str:
        """Genera firma HMAC-SHA256 del payload."""
        payload_str = json.dumps(self.to_dict(), sort_keys=True)
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature


class WebhookDeliveryAttempt(BaseModel):
    """Registro de intento de entrega de webhook."""
    attempt_number: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: WebhookDeliveryStatus
    http_status_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None


class WebhookDelivery(BaseModel):
    """Registro completo de entrega de webhook."""
    id: str
    endpoint_id: str
    payload: WebhookPayload
    status: WebhookStatus = WebhookStatus.PENDING
    attempts: List[WebhookDeliveryAttempt] = Field(default_factory=list)
    next_retry_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def last_attempt(self) -> Optional[WebhookDeliveryAttempt]:
        return self.attempts[-1] if self.attempts else None


# ============ Webhook Subscription ============

class CreateWebhookEndpoint(BaseModel):
    """Request para crear endpoint de webhook."""
    url: HttpUrl
    events: List[WebhookEventType] = Field(default_factory=list)
    custom_headers: Dict[str, str] = Field(default_factory=dict)

    @field_validator('url')
    @classmethod
    def validate_https(cls, v):
        if not str(v).startswith('https://'):
            raise ValueError('URL debe usar HTTPS')
        return str(v)


class WebhookEndpointResponse(BaseModel):
    """Respuesta al crear endpoint."""
    id: str
    url: str
    secret: str
    events: List[str]
    is_active: bool
    created_at: datetime


class UpdateWebhookEndpoint(BaseModel):
    """Request para actualizar endpoint."""
    url: Optional[HttpUrl] = None
    events: Optional[List[WebhookEventType]] = None
    is_active: Optional[bool] = None
    custom_headers: Optional[Dict[str, str]] = None


# ============ Webhook Log/Audit ============

class WebhookLogEntry(BaseModel):
    """Entrada de log de webhook."""
    id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: WebhookSource
    event_type: WebhookEventType
    direction: str  # "inbound" o "outbound"

    # Request info
    endpoint_url: Optional[str] = None
    request_headers: Dict[str, str] = Field(default_factory=dict)
    request_body: Optional[str] = None

    # Response info
    response_status: Optional[int] = None
    response_body: Optional[str] = None

    # Processing
    processed: bool = False
    processing_error: Optional[str] = None

    # Referencias
    remittance_id: Optional[str] = None
    tracking_key: Optional[str] = None
    order_id: Optional[str] = None


# ============ Event Payloads ============

class RemittanceWebhookData(BaseModel):
    """Datos de remesa para webhook."""
    remittance_id: str
    reference_code: str
    status: str
    amount_source: Decimal
    currency_source: str
    amount_destination: Decimal
    currency_destination: str
    recipient_name: str
    created_at: datetime
    updated_at: datetime

    # Detalles opcionales segun evento
    tx_hash: Optional[str] = None
    spei_tracking_key: Optional[str] = None
    bitso_order_id: Optional[str] = None
    error_message: Optional[str] = None


class SPEIStatusWebhookData(BaseModel):
    """Datos de estado SPEI para webhook."""
    tracking_key: str
    status: str  # liquidated, returned, cancelled
    amount: Decimal
    beneficiary_clabe: str
    beneficiary_name: str
    reference: Optional[str] = None
    return_reason: Optional[str] = None
    liquidated_at: Optional[datetime] = None


class BitsoStatusWebhookData(BaseModel):
    """Datos de estado Bitso para webhook."""
    order_id: Optional[str] = None
    withdrawal_id: Optional[str] = None
    status: str
    amount: Decimal
    currency: str
    rate: Optional[Decimal] = None
    fee: Optional[Decimal] = None


# ============ Signature Verification ============

class WebhookSignatureVerifier:
    """Utilidad para verificar firmas de webhooks."""

    @staticmethod
    def verify_stp_signature(
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """Verifica firma de webhook STP."""
        expected = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def verify_bitso_signature(
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """Verifica firma de webhook Bitso."""
        expected = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def generate_signature(
        payload: Dict[str, Any],
        secret: str,
    ) -> str:
        """Genera firma para webhook saliente."""
        payload_str = json.dumps(payload, sort_keys=True)
        return hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()


# ============ Constants ============

# Codigos de devolucion STP
STP_RETURN_CODES = {
    1: "Cuenta inexistente",
    2: "Cuenta bloqueada",
    3: "Cuenta cancelada",
    4: "Nombre no coincide",
    5: "RFC no coincide",
    6: "Orden duplicada",
    7: "Cuenta no permite recepcion",
    8: "Tipo de cuenta invalido",
    9: "Excede limite de monto",
    10: "Error de formato",
    99: "Otro",
}

# Estados de operacion STP
STP_OPERATION_STATES = {
    0: "Liquidado",
    1: "Pendiente",
    2: "Devuelto",
    3: "Cancelado",
    4: "En proceso",
}
