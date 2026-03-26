"""
Modelos de Remesas Blockchain para FinCore.

Sistema de transferencias transfronterizas con:
- Escrow en stablecoins (USDC/USDT)
- Time-lock de 48h para reembolsos automaticos
- Conciliacion con saldos fiat
- Trazabilidad completa on-chain

Cumple con PRD: Sistema Blockchain Fintech (Remesas)
"""
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Numeric,
    Text,
    ForeignKey,
    Enum as SQLEnum,
    Integer,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


# ============ Enums ============

class RemittanceStatus(str, Enum):
    """Estados del proceso de remesa (lado fiat)."""
    INITIATED = "initiated"          # Usuario inicio la remesa
    PENDING_DEPOSIT = "pending_deposit"  # Esperando deposito fiat del sender
    DEPOSITED = "deposited"          # Fiat recibido, pendiente conversion
    LOCKED = "locked"                # Stablecoins bloqueados en escrow
    PROCESSING = "processing"        # En proceso de liquidacion
    DISBURSED = "disbursed"          # Fondos entregados al beneficiario
    COMPLETED = "completed"          # Remesa completada exitosamente
    REFUND_PENDING = "refund_pending"  # Reembolso en proceso
    REFUNDED = "refunded"            # Reembolsado al sender
    FAILED = "failed"                # Fallo en el proceso
    CANCELLED = "cancelled"          # Cancelada por usuario
    EXPIRED = "expired"              # Expiro el time-lock


class BlockchainRemittanceStatus(str, Enum):
    """Estados de la transaccion blockchain."""
    PENDING = "pending"              # Transaccion creada, no enviada
    SUBMITTED = "submitted"          # Enviada a la red
    MINED = "mined"                  # Incluida en bloque
    CONFIRMED = "confirmed"          # Confirmaciones suficientes
    REVERTED = "reverted"            # Transaccion revertida
    REPLACED = "replaced"            # Reemplazada por otra tx


class PaymentMethod(str, Enum):
    """Metodos de pago para deposito fiat."""
    SPEI = "spei"                    # Mexico
    WIRE_TRANSFER = "wire_transfer"  # Internacional
    CARD = "card"                    # Tarjeta debito/credito
    CASH = "cash"                    # Efectivo en punto de pago
    CRYPTO = "crypto"                # Pago directo en crypto


class DisbursementMethod(str, Enum):
    """Metodos de entrega al beneficiario."""
    BANK_TRANSFER = "bank_transfer"  # Transferencia bancaria
    MOBILE_WALLET = "mobile_wallet"  # Wallet movil (ej: Mercado Pago)
    CASH_PICKUP = "cash_pickup"      # Retiro en efectivo
    HOME_DELIVERY = "home_delivery"  # Entrega a domicilio


class Currency(str, Enum):
    """Monedas soportadas."""
    MXN = "MXN"
    USD = "USD"
    EUR = "EUR"
    CLP = "CLP"  # Chile
    COP = "COP"  # Colombia
    PEN = "PEN"  # Peru
    BRL = "BRL"  # Brasil
    ARS = "ARS"  # Argentina


class Stablecoin(str, Enum):
    """Stablecoins soportados para escrow."""
    USDC = "USDC"
    USDT = "USDT"
    DAI = "DAI"


# ============ Modelos ============

class Remittance(Base):
    """
    Registro principal de remesa.

    Flujo:
    1. Sender inicia remesa (INITIATED)
    2. Sender deposita fiat (DEPOSITED)
    3. Sistema convierte a stablecoin y bloquea en escrow (LOCKED)
    4. Operador valida entrega fiat al beneficiario
    5. Sistema libera escrow (DISBURSED -> COMPLETED)

    Si no se completa en 48h, se activa reembolso automatico.
    """
    __tablename__ = "remittances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Referencia externa (para el usuario)
    reference_code = Column(String(20), unique=True, nullable=False, index=True)

    # Participantes
    sender_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)

    # Informacion del beneficiario (JSONB para flexibilidad por pais)
    # Estructura: {name, bank_name, account_number, account_type, clabe, iban, swift, phone, email, address}
    recipient_info = Column(JSONB, nullable=False)

    # Montos origen
    amount_fiat_source = Column(Numeric(18, 2), nullable=False)  # Monto enviado
    currency_source = Column(SQLEnum(Currency, name="currency_enum", create_type=False), nullable=False)

    # Montos destino
    amount_fiat_destination = Column(Numeric(18, 2), nullable=True)  # Monto a entregar
    currency_destination = Column(SQLEnum(Currency, name="currency_enum", create_type=False), nullable=False)

    # Conversion a stablecoin
    amount_stablecoin = Column(Numeric(18, 6), nullable=True)  # Monto en USDC/USDT
    stablecoin = Column(SQLEnum(Stablecoin, name="stablecoin_enum", create_type=False), default=Stablecoin.USDC)

    # Tasas de cambio
    exchange_rate_source_usd = Column(Numeric(18, 8), nullable=True)  # MXN -> USD
    exchange_rate_usd_destination = Column(Numeric(18, 8), nullable=True)  # USD -> destino
    exchange_rate_locked_at = Column(DateTime(timezone=True), nullable=True)

    # Comisiones
    platform_fee = Column(Numeric(18, 2), default=0)  # Fee de plataforma
    network_fee = Column(Numeric(18, 6), default=0)   # Gas fees blockchain
    total_fees = Column(Numeric(18, 2), default=0)

    # Estado
    status = Column(
        SQLEnum(RemittanceStatus, name="remittance_status_enum", create_type=False),
        default=RemittanceStatus.INITIATED,
        nullable=False,
        index=True
    )

    # Metodos de pago/entrega
    payment_method = Column(SQLEnum(PaymentMethod, name="payment_method_enum", create_type=False), nullable=True)
    disbursement_method = Column(SQLEnum(DisbursementMethod, name="disbursement_method_enum", create_type=False), nullable=True)

    # Time-lock para reembolso automatico (48h desde lock)
    escrow_locked_at = Column(DateTime(timezone=True), nullable=True)
    escrow_expires_at = Column(DateTime(timezone=True), nullable=True)  # locked_at + 48h

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata adicional
    notes = Column(Text, nullable=True)
    extra_data = Column(JSONB, default={})  # renamed from 'metadata' (reserved in SQLAlchemy)

    # IP y dispositivo para compliance
    sender_ip = Column(String(45), nullable=True)
    sender_device_fingerprint = Column(String(255), nullable=True)

    # Relaciones
    sender = relationship("User", foreign_keys=[sender_id], backref="remittances_sent")
    blockchain_transactions = relationship("RemittanceBlockchainTx", back_populates="remittance", cascade="all, delete-orphan")

    # Indices
    __table_args__ = (
        Index("ix_remittances_sender_status", "sender_id", "status"),
        Index("ix_remittances_created_at", "created_at"),
        Index("ix_remittances_escrow_expires", "escrow_expires_at"),
        CheckConstraint("amount_fiat_source > 0", name="check_positive_amount"),
    )


class RemittanceBlockchainTx(Base):
    """
    Transacciones blockchain asociadas a una remesa.

    Cada remesa puede tener multiples transacciones:
    - Lock inicial en escrow
    - Release al completar
    - Refund si expira
    - Reintentos por gas insuficiente
    """
    __tablename__ = "remittance_blockchain_txs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Relacion con remesa
    remittance_id = Column(UUID(as_uuid=True), ForeignKey("remittances.id", ondelete="CASCADE"), nullable=False)

    # Datos de transaccion
    tx_hash = Column(String(66), unique=True, nullable=True, index=True)  # 0x + 64 chars

    # Tipo de operacion
    operation = Column(String(50), nullable=False)  # lock, release, refund

    # Estado blockchain
    blockchain_status = Column(
        SQLEnum(BlockchainRemittanceStatus, name="blockchain_remittance_status_enum", create_type=False),
        default=BlockchainRemittanceStatus.PENDING,
        nullable=False
    )

    # Red y contrato
    network = Column(String(50), nullable=False, default="polygon")
    contract_address = Column(String(42), nullable=True)

    # Detalles de la transaccion
    from_address = Column(String(42), nullable=True)
    to_address = Column(String(42), nullable=True)
    value_wei = Column(Numeric(38, 0), default=0)  # Valor en wei

    # Gas
    gas_limit = Column(Integer, nullable=True)
    gas_used = Column(Integer, nullable=True)
    gas_price_gwei = Column(Numeric(18, 9), nullable=True)

    # Nonce para manejo de colas
    nonce = Column(Integer, nullable=True)

    # Bloque
    block_number = Column(Integer, nullable=True)
    block_timestamp = Column(DateTime(timezone=True), nullable=True)
    confirmations = Column(Integer, default=0)

    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    # Relacion
    remittance = relationship("Remittance", back_populates="blockchain_transactions")

    # Indices
    __table_args__ = (
        Index("ix_remittance_tx_status", "remittance_id", "blockchain_status"),
        Index("ix_remittance_tx_hash", "tx_hash"),
    )


class ReconciliationLog(Base):
    """
    Log de conciliacion entre:
    - Saldos en Ledger Interno (Postgres)
    - Saldos en Smart Contract (On-chain)
    - Saldos en Cuentas Bancarias (Fiat)

    Se ejecuta automaticamente cada 60 minutos.
    Alerta inmediatamente si hay discrepancia > $0.
    """
    __tablename__ = "reconciliation_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Timestamp del check
    check_timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Saldos esperados vs actuales
    # Ledger interno
    expected_balance_ledger = Column(Numeric(18, 6), nullable=False)
    actual_balance_ledger = Column(Numeric(18, 6), nullable=False)

    # On-chain (smart contract)
    expected_balance_onchain = Column(Numeric(18, 6), nullable=False)
    actual_balance_onchain = Column(Numeric(18, 6), nullable=False)

    # Fiat (cuentas bancarias)
    expected_balance_fiat = Column(Numeric(18, 2), nullable=True)
    actual_balance_fiat = Column(Numeric(18, 2), nullable=True)

    # Discrepancias
    discrepancy_ledger = Column(Numeric(18, 6), default=0)
    discrepancy_onchain = Column(Numeric(18, 6), default=0)
    discrepancy_fiat = Column(Numeric(18, 2), default=0)

    # Resultado
    discrepancy_detected = Column(Boolean, default=False)

    # Red y stablecoin verificados
    network = Column(String(50), nullable=False, default="polygon")
    stablecoin = Column(String(10), nullable=False, default="USDC")
    contract_address = Column(String(42), nullable=True)

    # Detalles del error si existe
    error_payload = Column(JSONB, default={})

    # Accion tomada
    action_taken = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    # Indices
    __table_args__ = (
        Index("ix_reconciliation_timestamp", "check_timestamp"),
        Index("ix_reconciliation_discrepancy", "discrepancy_detected"),
    )


class RemittanceLimit(Base):
    """
    Limites de remesas por nivel KYC y corredor.

    Ejemplo:
    - KYC Level 1: Max $1,000 USD/mes
    - KYC Level 2: Max $5,000 USD/mes
    - KYC Level 3: Sin limite
    """
    __tablename__ = "remittance_limits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Corredor (origen -> destino)
    corridor_source = Column(SQLEnum(Currency, name="currency_enum", create_type=False), nullable=False)
    corridor_destination = Column(SQLEnum(Currency, name="currency_enum", create_type=False), nullable=False)

    # Nivel KYC
    kyc_level = Column(Integer, nullable=False)  # 0, 1, 2, 3

    # Limites
    min_amount_usd = Column(Numeric(18, 2), default=10)       # Minimo por transaccion
    max_amount_usd = Column(Numeric(18, 2), default=1000)     # Maximo por transaccion
    daily_limit_usd = Column(Numeric(18, 2), default=1000)    # Limite diario
    monthly_limit_usd = Column(Numeric(18, 2), default=5000)  # Limite mensual

    # Estado
    is_active = Column(Boolean, default=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_limits_corridor", "corridor_source", "corridor_destination", "kyc_level"),
    )


class ExchangeRateHistory(Base):
    """
    Historial de tasas de cambio para auditoria y trazabilidad.
    """
    __tablename__ = "exchange_rate_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    currency_from = Column(SQLEnum(Currency, name="currency_enum", create_type=False), nullable=False)
    currency_to = Column(SQLEnum(Currency, name="currency_enum", create_type=False), nullable=False)

    rate = Column(Numeric(18, 8), nullable=False)
    rate_source = Column(String(50), nullable=False)  # "binance", "coinbase", "banxico", etc.

    captured_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_exchange_rate_currencies", "currency_from", "currency_to", "captured_at"),
    )
