"""
Ledger Inmutable - Libro Mayor de Grado Bancario.
Implementa patrón WORM (Write Once, Read Many) con verificación criptográfica.

Características:
- Solo INSERT permitido, nunca UPDATE ni DELETE
- Cada registro tiene hash SHA-256 que incluye el hash anterior (cadena)
- Detección automática de manipulación
- Compatible con auditorías SOC2 y ISO 27001
"""
import uuid
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from sqlalchemy import (
    Column, String, DateTime, Text, Numeric, Boolean,
    ForeignKey, event, DDL, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship, Session
from sqlalchemy.schema import Index
from sqlalchemy.ext.hybrid import hybrid_property

from app.core.database import Base


class LedgerEntryType:
    """Tipos de entrada en el ledger."""
    # Inversiones
    INVESTMENT_CREATED = "INVESTMENT_CREATED"
    INVESTMENT_CONFIRMED = "INVESTMENT_CONFIRMED"
    INVESTMENT_CANCELLED = "INVESTMENT_CANCELLED"

    # Pagos
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    PAYMENT_DISBURSED = "PAYMENT_DISBURSED"

    # Retornos
    INTEREST_ACCRUED = "INTEREST_ACCRUED"
    PRINCIPAL_RETURNED = "PRINCIPAL_RETURNED"
    DIVIDEND_PAID = "DIVIDEND_PAID"

    # Ajustes
    FEE_CHARGED = "FEE_CHARGED"
    REFUND_ISSUED = "REFUND_ISSUED"
    ADJUSTMENT = "ADJUSTMENT"


class ImmutableLedger(Base):
    """
    Libro Mayor Inmutable con Cadena de Hashes.

    Cada entrada contiene:
    - Hash del registro anterior (cadena de integridad)
    - Hash propio calculado de todos los campos
    - Timestamp de creación inmutable

    IMPORTANTE: Esta tabla tiene triggers SQL que previenen UPDATE y DELETE.
    """
    __tablename__ = "immutable_ledger"

    # Identificador único
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Número de secuencia (auto-incremento para ordenamiento)
    sequence_number = Column(Numeric(20, 0), nullable=False, unique=True)

    # Hash del registro anterior (NULL solo para el primer registro)
    previous_hash = Column(String(64), nullable=True)

    # Hash de este registro (calculado al crear)
    entry_hash = Column(String(64), nullable=False, unique=True)

    # Tipo de transacción
    entry_type = Column(String(50), nullable=False)

    # Referencias
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("proyectos.id"), nullable=True)
    investment_id = Column(UUID(as_uuid=True), ForeignKey("inversiones.id"), nullable=True)

    # Montos
    amount = Column(Numeric(18, 4), nullable=False)
    currency = Column(String(3), default="MXN", nullable=False)

    # Balance después de la transacción (para reconciliación)
    balance_after = Column(Numeric(18, 4), nullable=True)

    # Datos adicionales (cifrados si son sensibles)
    extra_data = Column(JSONB, nullable=True)

    # Contexto de auditoría
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    device_fingerprint = Column(String(64), nullable=True)

    # Descripción legible
    description = Column(Text, nullable=True)

    # Timestamp inmutable
    created_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    # Flag de verificación
    is_verified = Column(Boolean, default=True)
    verification_timestamp = Column(DateTime(timezone=True), nullable=True)

    # Relaciones
    user = relationship("User", foreign_keys=[user_id])
    project = relationship("Project", foreign_keys=[project_id])
    investment = relationship("Investment", foreign_keys=[investment_id])

    __table_args__ = (
        # Índices para consultas rápidas
        Index("idx_ledger_sequence", "sequence_number"),
        Index("idx_ledger_user", "user_id"),
        Index("idx_ledger_project", "project_id"),
        Index("idx_ledger_investment", "investment_id"),
        Index("idx_ledger_type", "entry_type"),
        Index("idx_ledger_created", "created_at"),
        Index("idx_ledger_hash", "entry_hash"),
        # Constraint para asegurar que amount no sea negativo para ciertos tipos
        CheckConstraint(
            "entry_type NOT IN ('PAYMENT_RECEIVED', 'INVESTMENT_CONFIRMED') OR amount >= 0",
            name="chk_positive_amounts"
        ),
    )

    @classmethod
    def calculate_hash(cls, data: Dict[str, Any]) -> str:
        """
        Calcula hash SHA-256 de los datos de la entrada.
        El hash incluye todos los campos críticos para detectar cualquier alteración.
        """
        # Campos que forman parte del hash
        hash_content = {
            "previous_hash": data.get("previous_hash", ""),
            "entry_type": data.get("entry_type"),
            "user_id": str(data.get("user_id", "")),
            "project_id": str(data.get("project_id", "")),
            "investment_id": str(data.get("investment_id", "")),
            "amount": str(data.get("amount")),
            "currency": data.get("currency", "MXN"),
            "balance_after": str(data.get("balance_after", "")),
            "created_at": data.get("created_at").isoformat() if data.get("created_at") else "",
            "description": data.get("description", ""),
        }

        # Serializar de forma determinística
        content_str = json.dumps(hash_content, sort_keys=True, default=str)

        # Calcular SHA-256
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()

    @classmethod
    def get_latest_entry(cls, db: Session) -> Optional["ImmutableLedger"]:
        """Obtiene la última entrada del ledger."""
        return db.query(cls).order_by(cls.sequence_number.desc()).first()

    @classmethod
    def get_next_sequence(cls, db: Session) -> int:
        """Obtiene el siguiente número de secuencia."""
        latest = cls.get_latest_entry(db)
        if latest:
            return int(latest.sequence_number) + 1
        return 1

    @classmethod
    def create_entry(
        cls,
        db: Session,
        entry_type: str,
        amount: Decimal,
        user_id: Optional[uuid.UUID] = None,
        project_id: Optional[uuid.UUID] = None,
        investment_id: Optional[uuid.UUID] = None,
        currency: str = "MXN",
        balance_after: Optional[Decimal] = None,
        extra_data: Optional[Dict] = None,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_fingerprint: Optional[str] = None
    ) -> "ImmutableLedger":
        """
        Crea una nueva entrada en el ledger con hash calculado.

        Esta es la ÚNICA forma de crear entradas en el ledger.
        """
        # Obtener último hash
        latest = cls.get_latest_entry(db)
        previous_hash = latest.entry_hash if latest else None

        # Preparar datos
        created_at = datetime.utcnow()
        sequence = cls.get_next_sequence(db)

        entry_data = {
            "previous_hash": previous_hash,
            "entry_type": entry_type,
            "user_id": user_id,
            "project_id": project_id,
            "investment_id": investment_id,
            "amount": amount,
            "currency": currency,
            "balance_after": balance_after,
            "created_at": created_at,
            "description": description,
        }

        # Calcular hash
        entry_hash = cls.calculate_hash(entry_data)

        # Crear entrada
        entry = cls(
            sequence_number=sequence,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            entry_type=entry_type,
            user_id=user_id,
            project_id=project_id,
            investment_id=investment_id,
            amount=amount,
            currency=currency,
            balance_after=balance_after,
            extra_data=extra_data,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            created_at=created_at,
            is_verified=True,
            verification_timestamp=datetime.utcnow()
        )

        db.add(entry)
        return entry

    @classmethod
    def verify_chain_integrity(cls, db: Session) -> Dict[str, Any]:
        """
        Verifica la integridad de toda la cadena del ledger.

        Retorna:
        - is_valid: bool
        - entries_verified: int
        - first_invalid_entry: Optional[int] (sequence_number)
        - error_message: Optional[str]
        """
        entries = db.query(cls).order_by(cls.sequence_number).all()

        if not entries:
            return {
                "is_valid": True,
                "entries_verified": 0,
                "first_invalid_entry": None,
                "error_message": None
            }

        previous_hash = None

        for entry in entries:
            # Verificar que previous_hash coincida
            if entry.previous_hash != previous_hash:
                return {
                    "is_valid": False,
                    "entries_verified": int(entry.sequence_number) - 1,
                    "first_invalid_entry": int(entry.sequence_number),
                    "error_message": f"Previous hash mismatch at sequence {entry.sequence_number}"
                }

            # Recalcular hash y verificar
            entry_data = {
                "previous_hash": entry.previous_hash,
                "entry_type": entry.entry_type,
                "user_id": entry.user_id,
                "project_id": entry.project_id,
                "investment_id": entry.investment_id,
                "amount": entry.amount,
                "currency": entry.currency,
                "balance_after": entry.balance_after,
                "created_at": entry.created_at,
                "description": entry.description,
            }

            calculated_hash = cls.calculate_hash(entry_data)

            if calculated_hash != entry.entry_hash:
                return {
                    "is_valid": False,
                    "entries_verified": int(entry.sequence_number) - 1,
                    "first_invalid_entry": int(entry.sequence_number),
                    "error_message": f"Hash mismatch at sequence {entry.sequence_number}. Data may have been tampered."
                }

            previous_hash = entry.entry_hash

        return {
            "is_valid": True,
            "entries_verified": len(entries),
            "first_invalid_entry": None,
            "error_message": None
        }

    def __repr__(self):
        return f"<LedgerEntry #{self.sequence_number} {self.entry_type} {self.amount}>"


# SQL Trigger para prevenir UPDATE y DELETE
# Este trigger se ejecutará a nivel de base de datos para máxima seguridad
PREVENT_UPDATE_TRIGGER = DDL("""
CREATE OR REPLACE FUNCTION prevent_ledger_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'UPDATE operations are not allowed on immutable_ledger table';
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'DELETE operations are not allowed on immutable_ledger table';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS prevent_ledger_update_delete ON immutable_ledger;

CREATE TRIGGER prevent_ledger_update_delete
BEFORE UPDATE OR DELETE ON immutable_ledger
FOR EACH ROW
EXECUTE FUNCTION prevent_ledger_modification();
""")

# Registrar el trigger para ejecutarse después de crear la tabla
event.listen(
    ImmutableLedger.__table__,
    'after_create',
    PREVENT_UPDATE_TRIGGER.execute_if(dialect='postgresql')
)


class LedgerSnapshot(Base):
    """
    Snapshots periódicos del estado del ledger para verificación rápida.
    Se generan automáticamente cada N transacciones o cada día.
    """
    __tablename__ = "ledger_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Referencia al último registro incluido en el snapshot
    last_sequence_number = Column(Numeric(20, 0), nullable=False)
    last_entry_hash = Column(String(64), nullable=False)

    # Hash del snapshot (hash de todos los hashes del período)
    snapshot_hash = Column(String(64), nullable=False, unique=True)

    # Totales para reconciliación rápida
    total_entries = Column(Numeric(20, 0), nullable=False)
    total_amount_in = Column(Numeric(18, 4), nullable=False)
    total_amount_out = Column(Numeric(18, 4), nullable=False)
    net_balance = Column(Numeric(18, 4), nullable=False)

    # Período cubierto
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_by = Column(String(100), default="SYSTEM")

    __table_args__ = (
        Index("idx_snapshot_sequence", "last_sequence_number"),
        Index("idx_snapshot_period", "period_start", "period_end"),
    )
