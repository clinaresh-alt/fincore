"""
Modelos de Inversiones y Transacciones.
Registro de participaciones de inversionistas en proyectos.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Text, ForeignKey,
    Enum as SQLEnum, Numeric
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Index
import enum

from app.core.database import Base


class InvestmentStatus(str, enum.Enum):
    """Estados de la inversion."""
    PENDIENTE = "Pendiente"       # Esperando confirmacion de pago
    ACTIVA = "Activa"             # Inversion confirmada
    EN_RENDIMIENTO = "En Rendimiento"  # Generando retornos
    LIQUIDADA = "Liquidada"       # Capital + rendimientos devueltos
    CANCELADA = "Cancelada"


class TransactionType(str, enum.Enum):
    """Tipos de transaccion."""
    APORTACION = "Aportacion"         # Inversion inicial
    RENDIMIENTO = "Rendimiento"       # Pago de intereses
    RETIRO_PARCIAL = "Retiro Parcial"
    LIQUIDACION = "Liquidacion"       # Devolucion total
    COMISION = "Comision"


class Investment(Base):
    """
    Inversiones de usuarios en proyectos.
    Relaciona inversionistas con proyectos.
    """
    __tablename__ = "inversiones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Relaciones
    inversionista_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False
    )
    proyecto_id = Column(
        UUID(as_uuid=True),
        ForeignKey("proyectos.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Montos
    monto_invertido = Column(Numeric(18, 2), nullable=False)
    monto_rendimiento_acumulado = Column(Numeric(18, 2), default=0)
    monto_total_recibido = Column(Numeric(18, 2), default=0)

    # Porcentaje de participacion
    porcentaje_participacion = Column(Numeric(7, 4), nullable=True)

    # Estado
    estado = Column(
        SQLEnum(InvestmentStatus, name="investment_status_enum"),
        default=InvestmentStatus.PENDIENTE
    )

    # Fechas
    fecha_inversion = Column(DateTime(timezone=True), default=datetime.utcnow)
    fecha_vencimiento = Column(DateTime(timezone=True), nullable=True)
    fecha_liquidacion = Column(DateTime(timezone=True), nullable=True)

    # Referencia de pago
    referencia_pago = Column(String(100), nullable=True)
    metodo_pago = Column(String(50), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    # Relaciones
    investor = relationship("User", back_populates="investments")
    project = relationship("Project", back_populates="inversiones")
    transactions = relationship("InvestmentTransaction", back_populates="investment")

    __table_args__ = (
        Index("idx_inversion_inversionista", "inversionista_id"),
        Index("idx_inversion_proyecto", "proyecto_id"),
        Index("idx_inversion_estado", "estado"),
    )

    @property
    def rendimiento_total(self) -> float:
        """Calcula el rendimiento porcentual total."""
        if self.monto_invertido and self.monto_invertido > 0:
            return float(
                (self.monto_total_recibido - self.monto_invertido) / self.monto_invertido
            )
        return 0.0

    def __repr__(self):
        return f"<Investment {self.monto_invertido} en {self.proyecto_id}>"


class InvestmentTransaction(Base):
    """
    Historial de transacciones de cada inversion.
    Permite tracking completo de flujos.
    """
    __tablename__ = "transacciones_inversion"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    inversion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inversiones.id", ondelete="CASCADE"),
        nullable=False
    )

    # Tipo y monto
    tipo = Column(
        SQLEnum(TransactionType, name="transaction_type_enum"),
        nullable=False
    )
    monto = Column(Numeric(18, 2), nullable=False)

    # Referencia externa (banco, pasarela de pago)
    referencia_externa = Column(String(255), nullable=True)

    # Descripcion
    concepto = Column(String(255), nullable=True)
    notas = Column(Text, nullable=True)

    # Fecha de la transaccion
    fecha_transaccion = Column(DateTime(timezone=True), default=datetime.utcnow)
    fecha_valor = Column(DateTime(timezone=True), nullable=True)  # Fecha de liquidacion

    # Relaciones
    investment = relationship("Investment", back_populates="transactions")

    __table_args__ = (
        Index("idx_transaccion_inversion", "inversion_id"),
        Index("idx_transaccion_tipo", "tipo"),
        Index("idx_transaccion_fecha", "fecha_transaccion"),
    )

    def __repr__(self):
        return f"<Transaction {self.tipo}: {self.monto}>"
