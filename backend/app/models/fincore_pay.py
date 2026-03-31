"""
Modelos para Fincore Pay - Pagos P2P y QR.
Sistema de pagos instantáneos entre usuarios.
"""
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey,
    Text, Numeric, Enum as SQLEnum, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid
import enum
import secrets
import hashlib
import qrcode
import io
import base64

from app.core.database import Base


class P2PTransferStatus(str, enum.Enum):
    """Estado de transferencia P2P."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentRequestStatus(str, enum.Enum):
    """Estado de solicitud de pago."""
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    DECLINED = "declined"


class QRPaymentType(str, enum.Enum):
    """Tipo de pago QR."""
    STATIC = "static"  # QR fijo del comercio
    DYNAMIC = "dynamic"  # QR con monto específico
    ONE_TIME = "one_time"  # QR de un solo uso


class P2PTransfer(Base):
    """
    Transferencia P2P entre usuarios.
    Pagos instantáneos dentro de la plataforma.
    """
    __tablename__ = "p2p_transfers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transfer_number = Column(String(20), unique=True, nullable=False)

    # Participantes
    sender_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False
    )
    receiver_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Monto
    amount = Column(Numeric(18, 8), nullable=False)
    currency = Column(String(10), default="MXN")
    fee = Column(Numeric(18, 8), default=0)

    # Estado
    status = Column(
        SQLEnum(P2PTransferStatus, name="p2p_transfer_status_enum", create_type=False),
        default=P2PTransferStatus.PENDING
    )

    # Método de identificación del receptor
    receiver_identifier_type = Column(String(20))  # "phone", "email", "username", "wallet"
    receiver_identifier = Column(String(255))

    # Descripción/Concepto
    concept = Column(String(255))
    note = Column(Text)

    # Referencias
    reference_id = Column(String(50))  # Para pagos de servicios
    payment_request_id = Column(UUID(as_uuid=True), ForeignKey("payment_requests.id"), nullable=True)

    # Metadata
    metadata = Column(JSONB, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    sender = relationship("User", foreign_keys=[sender_id], backref="sent_p2p_transfers")
    receiver = relationship("User", foreign_keys=[receiver_id], backref="received_p2p_transfers")

    __table_args__ = (
        CheckConstraint("sender_id != receiver_id", name="check_different_users"),
        CheckConstraint("amount > 0", name="check_positive_amount"),
        Index("idx_p2p_sender", "sender_id"),
        Index("idx_p2p_receiver", "receiver_id"),
        Index("idx_p2p_status", "status"),
        Index("idx_p2p_created", "created_at"),
    )

    @staticmethod
    def generate_transfer_number() -> str:
        """Genera número de transferencia único."""
        timestamp = datetime.utcnow().strftime("%y%m%d%H%M%S")
        random_part = secrets.token_hex(3).upper()
        return f"P2P{timestamp}{random_part}"


class PaymentRequest(Base):
    """
    Solicitud de pago.
    Permite a usuarios solicitar pagos a otros.
    """
    __tablename__ = "payment_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_code = Column(String(20), unique=True, nullable=False)

    # Creador de la solicitud (quien recibirá el pago)
    requester_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )

    # Pagador (puede ser null si es solicitud abierta)
    payer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    # Monto
    amount = Column(Numeric(18, 8), nullable=False)
    currency = Column(String(10), default="MXN")

    # Detalles
    description = Column(String(255), nullable=False)
    note = Column(Text)

    # Estado
    status = Column(
        SQLEnum(PaymentRequestStatus, name="payment_request_status_enum", create_type=False),
        default=PaymentRequestStatus.PENDING
    )

    # Expiración
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Referencia al pago realizado
    transfer_id = Column(UUID(as_uuid=True), nullable=True)

    # Metadata
    metadata = Column(JSONB, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    requester = relationship("User", foreign_keys=[requester_id], backref="payment_requests_created")
    payer = relationship("User", foreign_keys=[payer_id], backref="payment_requests_received")

    __table_args__ = (
        CheckConstraint("amount > 0", name="check_request_positive_amount"),
        Index("idx_request_requester", "requester_id"),
        Index("idx_request_status", "status"),
    )

    @staticmethod
    def generate_request_code() -> str:
        """Genera código de solicitud único."""
        return secrets.token_urlsafe(12).upper()[:16]


class QRPayment(Base):
    """
    Pago mediante código QR.
    Soporta QR estáticos (comercios) y dinámicos (montos específicos).
    """
    __tablename__ = "qr_payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    qr_code = Column(String(64), unique=True, nullable=False)

    # Propietario del QR (receptor del pago)
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )

    # Tipo de QR
    qr_type = Column(
        SQLEnum(QRPaymentType, name="qr_payment_type_enum", create_type=False),
        default=QRPaymentType.DYNAMIC
    )

    # Monto (null para QR estáticos donde el pagador define el monto)
    amount = Column(Numeric(18, 8), nullable=True)
    currency = Column(String(10), default="MXN")

    # Para comercios
    merchant_name = Column(String(255), nullable=True)
    merchant_category = Column(String(50), nullable=True)

    # Descripción
    description = Column(String(255))

    # Estado y uso
    is_active = Column(Boolean, default=True)
    is_used = Column(Boolean, default=False)  # Para ONE_TIME
    use_count = Column(Integer, default=0)
    max_uses = Column(Integer, nullable=True)  # null = ilimitado

    # Límites
    min_amount = Column(Numeric(18, 8), nullable=True)
    max_amount = Column(Numeric(18, 8), nullable=True)

    # Expiración
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    owner = relationship("User", backref="qr_payments")
    transactions = relationship("QRTransaction", back_populates="qr_payment")

    __table_args__ = (
        Index("idx_qr_owner", "owner_id"),
        Index("idx_qr_code", "qr_code"),
        Index("idx_qr_active", "is_active"),
    )

    @staticmethod
    def generate_qr_code() -> str:
        """Genera código QR único."""
        return secrets.token_urlsafe(32)

    def generate_qr_image(self, base_url: str = "https://pay.fincore.com") -> str:
        """
        Genera imagen QR en base64.

        Args:
            base_url: URL base para el pago

        Returns:
            Imagen QR en formato base64
        """
        payment_url = f"{base_url}/qr/{self.qr_code}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(payment_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return base64.b64encode(buffer.getvalue()).decode("utf-8")


class QRTransaction(Base):
    """
    Transacción realizada mediante QR.
    """
    __tablename__ = "qr_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # QR usado
    qr_payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("qr_payments.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Pagador
    payer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Transferencia P2P generada
    p2p_transfer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("p2p_transfers.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Monto pagado
    amount = Column(Numeric(18, 8), nullable=False)
    currency = Column(String(10), default="MXN")

    # Metadata del dispositivo
    device_info = Column(JSONB, default={})
    location = Column(JSONB, default={})  # lat, lng si el usuario lo permite

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    qr_payment = relationship("QRPayment", back_populates="transactions")
    payer = relationship("User", backref="qr_transactions_made")
    p2p_transfer = relationship("P2PTransfer", backref="qr_transaction")

    __table_args__ = (
        Index("idx_qr_tx_qr", "qr_payment_id"),
        Index("idx_qr_tx_payer", "payer_id"),
        Index("idx_qr_tx_created", "created_at"),
    )


class ContactPayment(Base):
    """
    Contactos de pago frecuentes.
    Para pagos rápidos a contactos guardados.
    """
    __tablename__ = "contact_payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Usuario que guarda el contacto
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )

    # Contacto (puede ser usuario de la plataforma o externo)
    contact_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    # Identificador externo si no es usuario
    contact_name = Column(String(100), nullable=False)
    contact_identifier_type = Column(String(20))  # phone, email, clabe
    contact_identifier = Column(String(255))

    # Alias personalizado
    alias = Column(String(50))

    # Imagen/avatar del contacto
    avatar_url = Column(String(500))

    # Estadísticas
    payment_count = Column(Integer, default=0)
    total_amount_sent = Column(Numeric(18, 8), default=0)
    last_payment_at = Column(DateTime(timezone=True))

    # Estado
    is_favorite = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    user = relationship("User", foreign_keys=[user_id], backref="payment_contacts")
    contact_user = relationship("User", foreign_keys=[contact_user_id])

    __table_args__ = (
        Index("idx_contact_user", "user_id"),
        Index("idx_contact_favorite", "user_id", "is_favorite"),
    )
