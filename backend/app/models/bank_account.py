"""
Modelos de Cuentas Bancarias para FinCore.

Integración con sistemas bancarios mexicanos:
- SPEI (Sistema de Pagos Electrónicos Interbancarios) - Banco de México
- STP (Sistema de Transferencias y Pagos) - Cámara de compensación
- Transferencias Wire internacionales

Soporte para:
- Cuentas operativas de la plataforma (recepción/envío fiat)
- Cuentas de beneficiarios (payouts)
- Conciliación automática con el ledger interno
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


# ============ Enums ============

class BankProvider(str, Enum):
    """Proveedores de servicios bancarios."""
    STP = "stp"                    # STP - Sistema de Transferencias y Pagos
    SPEI_DIRECTO = "spei_directo"  # SPEI Directo (solo grandes instituciones)
    BANXICO = "banxico"            # Banco de México (solo referencia)
    ARCUS = "arcus"                # Arcus Fi (APIs para SPEI)
    CONEKTA = "conekta"            # Conekta (pasarela de pagos)
    OPENPAY = "openpay"            # OpenPay (pasarela de pagos)
    STRIPE = "stripe"              # Stripe (internacional)
    WISE = "wise"                  # Wise (transferencias internacionales)


class BankAccountType(str, Enum):
    """Tipos de cuenta bancaria."""
    CLABE = "clabe"                # CLABE interbancaria (18 dígitos) - México
    CUENTA = "cuenta"              # Número de cuenta interno del banco
    TARJETA = "tarjeta"            # Número de tarjeta de débito
    IBAN = "iban"                  # IBAN internacional
    SWIFT = "swift"                # Código SWIFT/BIC
    ACH = "ach"                    # ACH routing (USA)
    VIRTUAL = "virtual"            # Cuenta virtual (STP)


class BankAccountStatus(str, Enum):
    """Estados de cuenta bancaria."""
    PENDING_VERIFICATION = "pending_verification"  # Pendiente verificar
    ACTIVE = "active"                              # Activa y operativa
    SUSPENDED = "suspended"                        # Suspendida temporalmente
    CLOSED = "closed"                              # Cerrada
    BLOCKED = "blocked"                            # Bloqueada por compliance


class BankTransactionType(str, Enum):
    """Tipos de transacción bancaria."""
    DEPOSIT = "deposit"            # Depósito/Abono
    WITHDRAWAL = "withdrawal"      # Retiro/Cargo
    TRANSFER_IN = "transfer_in"    # Transferencia recibida (SPEI-IN)
    TRANSFER_OUT = "transfer_out"  # Transferencia enviada (SPEI-OUT)
    FEE = "fee"                    # Comisión bancaria
    INTEREST = "interest"          # Interés
    REVERSAL = "reversal"          # Reversa/Devolución
    ADJUSTMENT = "adjustment"      # Ajuste manual


class BankTransactionStatus(str, Enum):
    """Estados de transacción bancaria."""
    PENDING = "pending"            # Pendiente de procesamiento
    PROCESSING = "processing"      # En proceso (SPEI en tránsito)
    COMPLETED = "completed"        # Completada/Liquidada
    FAILED = "failed"              # Fallida
    CANCELLED = "cancelled"        # Cancelada
    REVERSED = "reversed"          # Reversada
    RETURNED = "returned"          # Devuelta


class SpeiOperationType(str, Enum):
    """Tipos de operación SPEI según Banxico."""
    SPEI_ORDINARIO = "ordinario"   # SPEI normal (segundos)
    SPEI_TERCEROS = "terceros"     # A terceros en mismo banco
    TEF = "tef"                    # Transferencia Electrónica de Fondos
    CCEN = "ccen"                  # Cámara de compensación


# ============ Modelos ============

class BankAccount(Base):
    """
    Cuenta bancaria registrada en el sistema.

    Puede ser:
    1. Cuenta operativa de FinCore (para recibir depósitos y enviar payouts)
    2. Cuenta de un usuario (para recibir payouts como beneficiario)
    3. Cuenta CLABE virtual generada por STP
    """
    __tablename__ = "bank_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identificador interno único
    account_alias = Column(String(100), unique=True, nullable=False)

    # Propietario (NULL si es cuenta operativa de la plataforma)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    is_platform_account = Column(Boolean, default=False)  # True = cuenta operativa FinCore

    # Datos bancarios
    bank_name = Column(String(100), nullable=False)
    bank_code = Column(String(10), nullable=True)  # Código banco (ej: "40012" para BBVA)

    # Tipo y número de cuenta
    account_type = Column(SQLEnum(BankAccountType, name="bank_account_type_enum", create_type=False), nullable=False)
    account_number = Column(String(50), nullable=False)  # CLABE, cuenta, IBAN, etc.
    account_number_masked = Column(String(50), nullable=True)  # Ej: ****1234

    # Para México (SPEI)
    clabe = Column(String(18), nullable=True, index=True)  # CLABE interbancaria

    # Para internacional
    swift_bic = Column(String(11), nullable=True)
    iban = Column(String(34), nullable=True)
    routing_number = Column(String(20), nullable=True)  # ACH/ABA

    # Moneda
    currency = Column(String(3), nullable=False, default="MXN")

    # Titular
    holder_name = Column(String(200), nullable=False)
    holder_rfc = Column(String(13), nullable=True)  # RFC en México
    holder_curp = Column(String(18), nullable=True)  # CURP en México

    # Proveedor de servicios
    provider = Column(SQLEnum(BankProvider, name="bank_provider_enum", create_type=False), nullable=True)
    provider_account_id = Column(String(100), nullable=True)  # ID en el sistema del proveedor

    # Estado
    status = Column(
        SQLEnum(BankAccountStatus, name="bank_account_status_enum", create_type=False),
        default=BankAccountStatus.PENDING_VERIFICATION,
        nullable=False
    )
    verified_at = Column(DateTime(timezone=True), nullable=True)

    # Balance (para cuentas operativas)
    last_known_balance = Column(Numeric(18, 2), default=0)
    balance_updated_at = Column(DateTime(timezone=True), nullable=True)

    # Límites
    daily_limit = Column(Numeric(18, 2), nullable=True)
    monthly_limit = Column(Numeric(18, 2), nullable=True)

    # Metadata
    extra_data = Column(JSONB, default={})
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    owner = relationship("User", foreign_keys=[owner_id], backref="bank_accounts")
    transactions = relationship("BankTransaction", back_populates="account", cascade="all, delete-orphan")

    # Índices
    __table_args__ = (
        Index("ix_bank_accounts_owner", "owner_id"),
        Index("ix_bank_accounts_clabe", "clabe"),
        Index("ix_bank_accounts_status", "status"),
        Index("ix_bank_accounts_platform", "is_platform_account"),
        UniqueConstraint("clabe", name="uq_bank_accounts_clabe"),
    )


class BankTransaction(Base):
    """
    Transacción bancaria registrada.

    Fuentes de datos:
    1. Webhook de STP/SPEI (tiempo real)
    2. Estado de cuenta bancario (conciliación batch)
    3. API de consulta de movimientos
    4. Registro manual (ajustes)
    """
    __tablename__ = "bank_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Cuenta asociada
    account_id = Column(UUID(as_uuid=True), ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False)

    # Referencia única de la transacción
    reference_id = Column(String(100), unique=True, nullable=False, index=True)

    # Referencia bancaria (clave de rastreo SPEI, etc.)
    bank_reference = Column(String(100), nullable=True, index=True)
    tracking_key = Column(String(30), nullable=True)  # Clave de rastreo SPEI (7 dígitos)

    # Tipo y dirección
    transaction_type = Column(
        SQLEnum(BankTransactionType, name="bank_transaction_type_enum", create_type=False),
        nullable=False
    )

    # Monto
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="MXN")

    # Balance después de la transacción
    balance_after = Column(Numeric(18, 2), nullable=True)

    # Estado
    status = Column(
        SQLEnum(BankTransactionStatus, name="bank_transaction_status_enum", create_type=False),
        default=BankTransactionStatus.PENDING,
        nullable=False
    )

    # Contraparte
    counterparty_name = Column(String(200), nullable=True)
    counterparty_bank = Column(String(100), nullable=True)
    counterparty_account = Column(String(50), nullable=True)
    counterparty_clabe = Column(String(18), nullable=True)
    counterparty_rfc = Column(String(13), nullable=True)

    # Concepto y descripción
    concept = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)

    # Relación con remesa (si aplica)
    remittance_id = Column(UUID(as_uuid=True), ForeignKey("remittances.id", ondelete="SET NULL"), nullable=True)

    # Tipo de operación SPEI
    spei_operation_type = Column(
        SQLEnum(SpeiOperationType, name="spei_operation_type_enum", create_type=False),
        nullable=True
    )

    # Datos del proveedor
    provider = Column(SQLEnum(BankProvider, name="bank_provider_enum", create_type=False), nullable=True)
    provider_transaction_id = Column(String(100), nullable=True)

    # Timestamps de la transacción
    transaction_date = Column(DateTime(timezone=True), nullable=False)  # Fecha/hora de la operación
    value_date = Column(DateTime(timezone=True), nullable=True)         # Fecha valor

    # Comisiones
    fee_amount = Column(Numeric(18, 2), default=0)

    # Error handling
    error_code = Column(String(20), nullable=True)
    error_message = Column(Text, nullable=True)

    # Metadata
    raw_data = Column(JSONB, default={})  # Datos crudos del webhook/API
    extra_data = Column(JSONB, default={})

    # Conciliación
    reconciled = Column(Boolean, default=False)
    reconciled_at = Column(DateTime(timezone=True), nullable=True)
    reconciliation_log_id = Column(UUID(as_uuid=True), ForeignKey("reconciliation_logs.id"), nullable=True)

    # Timestamps del sistema
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    account = relationship("BankAccount", back_populates="transactions")
    remittance = relationship("Remittance", backref="bank_transactions")

    # Índices
    __table_args__ = (
        Index("ix_bank_tx_account", "account_id"),
        Index("ix_bank_tx_date", "transaction_date"),
        Index("ix_bank_tx_status", "status"),
        Index("ix_bank_tx_type", "transaction_type"),
        Index("ix_bank_tx_remittance", "remittance_id"),
        Index("ix_bank_tx_reconciled", "reconciled"),
        Index("ix_bank_tx_tracking", "tracking_key"),
    )


class BankStatementImport(Base):
    """
    Registro de importación de estados de cuenta bancarios.

    Permite conciliación batch con archivos de movimientos
    descargados del portal bancario o recibidos por correo.
    """
    __tablename__ = "bank_statement_imports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Cuenta asociada
    account_id = Column(UUID(as_uuid=True), ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False)

    # Archivo importado
    filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)  # csv, xlsx, pdf, ofx
    file_hash = Column(String(64), nullable=True)   # SHA256 del archivo
    file_path = Column(String(500), nullable=True)  # Ruta en S3

    # Periodo del estado de cuenta
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)

    # Estadísticas
    total_records = Column(Integer, default=0)
    records_imported = Column(Integer, default=0)
    records_duplicated = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)

    # Montos
    total_debits = Column(Numeric(18, 2), default=0)
    total_credits = Column(Numeric(18, 2), default=0)
    opening_balance = Column(Numeric(18, 2), nullable=True)
    closing_balance = Column(Numeric(18, 2), nullable=True)

    # Estado
    import_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    error_log = Column(JSONB, default=[])

    # Quién importó
    imported_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relación
    account = relationship("BankAccount", backref="statement_imports")

    __table_args__ = (
        Index("ix_statement_import_account", "account_id"),
        Index("ix_statement_import_period", "period_start", "period_end"),
    )


class VirtualClabeAssignment(Base):
    """
    Asignación de CLABEs virtuales a remesas/usuarios.

    STP permite generar CLABEs virtuales para identificar
    cada depósito entrante de forma única.
    """
    __tablename__ = "virtual_clabe_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # CLABE virtual generada
    virtual_clabe = Column(String(18), unique=True, nullable=False, index=True)

    # A qué está asignada
    assignment_type = Column(String(20), nullable=False)  # "remittance", "user", "general"
    remittance_id = Column(UUID(as_uuid=True), ForeignKey("remittances.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)

    # Cuenta STP base
    base_account_id = Column(UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=False)

    # Estado
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Uso
    times_used = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    total_received = Column(Numeric(18, 2), default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    base_account = relationship("BankAccount")
    remittance = relationship("Remittance", backref="virtual_clabes")
    user = relationship("User", backref="virtual_clabes")

    __table_args__ = (
        Index("ix_virtual_clabe_assignment", "assignment_type", "remittance_id", "user_id"),
        Index("ix_virtual_clabe_active", "is_active"),
    )
