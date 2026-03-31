"""
Schemas para Fincore Pay - Pagos P2P y QR.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from enum import Enum


class P2PTransferStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentRequestStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    DECLINED = "declined"


class QRPaymentType(str, Enum):
    STATIC = "static"
    DYNAMIC = "dynamic"
    ONE_TIME = "one_time"


class ReceiverIdentifierType(str, Enum):
    PHONE = "phone"
    EMAIL = "email"
    USERNAME = "username"
    WALLET = "wallet"


# =====================
# P2P Transfer Schemas
# =====================

class P2PTransferCreate(BaseModel):
    """Crear transferencia P2P."""
    receiver_identifier_type: ReceiverIdentifierType
    receiver_identifier: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(..., gt=0, le=Decimal("500000"))
    currency: str = Field(default="MXN", max_length=10)
    concept: Optional[str] = Field(None, max_length=255)
    note: Optional[str] = None
    reference_id: Optional[str] = Field(None, max_length=50)

    @validator("amount")
    def validate_amount(cls, v):
        if v.as_tuple().exponent < -8:
            raise ValueError("Máximo 8 decimales permitidos")
        return v


class P2PTransferResponse(BaseModel):
    """Respuesta de transferencia P2P."""
    id: UUID
    transfer_number: str
    sender_id: UUID
    receiver_id: UUID
    amount: Decimal
    currency: str
    fee: Decimal
    status: P2PTransferStatus
    receiver_identifier_type: Optional[str]
    receiver_identifier: Optional[str]
    concept: Optional[str]
    note: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]
    completed_at: Optional[datetime]

    # Info del receptor (populated)
    receiver_name: Optional[str] = None
    receiver_avatar: Optional[str] = None

    class Config:
        from_attributes = True


class P2PTransferList(BaseModel):
    """Lista de transferencias P2P."""
    transfers: List[P2PTransferResponse]
    total: int
    page: int
    page_size: int


class P2PTransferCancel(BaseModel):
    """Cancelar transferencia P2P."""
    reason: Optional[str] = Field(None, max_length=255)


# =====================
# Payment Request Schemas
# =====================

class PaymentRequestCreate(BaseModel):
    """Crear solicitud de pago."""
    payer_identifier: Optional[str] = Field(None, max_length=255)
    payer_identifier_type: Optional[ReceiverIdentifierType] = None
    amount: Decimal = Field(..., gt=0, le=Decimal("500000"))
    currency: str = Field(default="MXN", max_length=10)
    description: str = Field(..., min_length=1, max_length=255)
    note: Optional[str] = None
    expires_in_hours: Optional[int] = Field(default=24, ge=1, le=720)


class PaymentRequestResponse(BaseModel):
    """Respuesta de solicitud de pago."""
    id: UUID
    request_code: str
    requester_id: UUID
    payer_id: Optional[UUID]
    amount: Decimal
    currency: str
    description: str
    note: Optional[str]
    status: PaymentRequestStatus
    expires_at: Optional[datetime]
    transfer_id: Optional[UUID]
    created_at: datetime
    paid_at: Optional[datetime]

    # Info del solicitante (populated)
    requester_name: Optional[str] = None
    requester_avatar: Optional[str] = None

    # Link de pago
    payment_link: Optional[str] = None

    class Config:
        from_attributes = True


class PaymentRequestList(BaseModel):
    """Lista de solicitudes de pago."""
    requests: List[PaymentRequestResponse]
    total: int
    page: int
    page_size: int


class PaymentRequestPay(BaseModel):
    """Pagar solicitud de pago."""
    note: Optional[str] = None


# =====================
# QR Payment Schemas
# =====================

class QRPaymentCreate(BaseModel):
    """Crear código QR de pago."""
    qr_type: QRPaymentType = QRPaymentType.DYNAMIC
    amount: Optional[Decimal] = Field(None, gt=0, le=Decimal("500000"))
    currency: str = Field(default="MXN", max_length=10)
    description: Optional[str] = Field(None, max_length=255)
    merchant_name: Optional[str] = Field(None, max_length=255)
    merchant_category: Optional[str] = Field(None, max_length=50)
    min_amount: Optional[Decimal] = Field(None, gt=0)
    max_amount: Optional[Decimal] = Field(None, gt=0)
    max_uses: Optional[int] = Field(None, ge=1)
    expires_in_minutes: Optional[int] = Field(None, ge=1, le=43200)

    @validator("amount")
    def validate_amount(cls, v, values):
        if values.get("qr_type") == QRPaymentType.DYNAMIC and v is None:
            raise ValueError("El monto es requerido para QR dinámico")
        return v


class QRPaymentResponse(BaseModel):
    """Respuesta de código QR."""
    id: UUID
    qr_code: str
    qr_type: QRPaymentType
    owner_id: UUID
    amount: Optional[Decimal]
    currency: str
    description: Optional[str]
    merchant_name: Optional[str]
    merchant_category: Optional[str]
    is_active: bool
    is_used: bool
    use_count: int
    max_uses: Optional[int]
    min_amount: Optional[Decimal]
    max_amount: Optional[Decimal]
    expires_at: Optional[datetime]
    created_at: datetime
    last_used_at: Optional[datetime]

    # QR image
    qr_image_base64: Optional[str] = None
    payment_url: Optional[str] = None

    class Config:
        from_attributes = True


class QRPaymentList(BaseModel):
    """Lista de códigos QR."""
    qr_codes: List[QRPaymentResponse]
    total: int
    page: int
    page_size: int


class QRPaymentScan(BaseModel):
    """Escanear código QR para pago."""
    qr_code: str = Field(..., min_length=1, max_length=64)


class QRPaymentScanResponse(BaseModel):
    """Respuesta de escaneo de QR."""
    qr_payment: QRPaymentResponse
    owner_name: str
    owner_avatar: Optional[str]
    can_pay: bool
    reason: Optional[str] = None


class QRPaymentExecute(BaseModel):
    """Ejecutar pago mediante QR."""
    qr_code: str = Field(..., min_length=1, max_length=64)
    amount: Optional[Decimal] = Field(None, gt=0)
    note: Optional[str] = None


class QRTransactionResponse(BaseModel):
    """Respuesta de transacción QR."""
    id: UUID
    qr_payment_id: UUID
    payer_id: UUID
    p2p_transfer_id: UUID
    amount: Decimal
    currency: str
    created_at: datetime

    # P2P transfer info
    transfer_number: Optional[str] = None
    transfer_status: Optional[str] = None

    class Config:
        from_attributes = True


# =====================
# Contact Schemas
# =====================

class ContactPaymentCreate(BaseModel):
    """Agregar contacto de pago."""
    contact_name: str = Field(..., min_length=1, max_length=100)
    contact_identifier_type: ReceiverIdentifierType
    contact_identifier: str = Field(..., min_length=1, max_length=255)
    alias: Optional[str] = Field(None, max_length=50)
    is_favorite: bool = False


class ContactPaymentUpdate(BaseModel):
    """Actualizar contacto de pago."""
    alias: Optional[str] = Field(None, max_length=50)
    is_favorite: Optional[bool] = None
    is_active: Optional[bool] = None


class ContactPaymentResponse(BaseModel):
    """Respuesta de contacto de pago."""
    id: UUID
    user_id: UUID
    contact_user_id: Optional[UUID]
    contact_name: str
    contact_identifier_type: Optional[str]
    contact_identifier: Optional[str]
    alias: Optional[str]
    avatar_url: Optional[str]
    payment_count: int
    total_amount_sent: Decimal
    last_payment_at: Optional[datetime]
    is_favorite: bool
    is_active: bool
    created_at: datetime

    # Si es usuario de la plataforma
    is_platform_user: bool = False

    class Config:
        from_attributes = True


class ContactPaymentList(BaseModel):
    """Lista de contactos de pago."""
    contacts: List[ContactPaymentResponse]
    total: int
    favorites: int


# =====================
# Analytics Schemas
# =====================

class PayAnalytics(BaseModel):
    """Analíticas de pagos."""
    total_sent: Decimal
    total_received: Decimal
    total_transactions: int
    transactions_sent: int
    transactions_received: int
    average_sent: Decimal
    average_received: Decimal
    most_paid_contacts: List[Dict[str, Any]]
    transactions_by_day: List[Dict[str, Any]]
    transactions_by_hour: List[Dict[str, Any]]


class PayLimits(BaseModel):
    """Límites de pago."""
    daily_limit: Decimal
    daily_used: Decimal
    daily_remaining: Decimal
    monthly_limit: Decimal
    monthly_used: Decimal
    monthly_remaining: Decimal
    single_transaction_limit: Decimal
    contacts_limit: int
    contacts_used: int
