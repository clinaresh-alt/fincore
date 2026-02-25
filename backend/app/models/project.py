"""
Modelos de Proyectos de Inversion y Evaluacion Financiera.
Incluye: VAN, TIR, Payback, Credit Scoring.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime,
    Text, ForeignKey, Enum as SQLEnum, Numeric, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Index
import enum

from app.core.database import Base


class ProjectStatus(str, enum.Enum):
    """Estados del ciclo de vida del proyecto."""
    EN_EVALUACION = "En Evaluacion"
    APROBADO = "Aprobado"
    RECHAZADO = "Rechazado"
    FINANCIANDO = "Financiando"
    FINANCIADO = "Financiado"
    EN_EJECUCION = "En Ejecucion"
    COMPLETADO = "Completado"
    DEFAULT = "Default"


class RiskLevel(str, enum.Enum):
    """Niveles de riesgo basados en Credit Score."""
    AAA = "AAA"  # 800-1000: Aprobacion automatica
    AA = "AA"    # 700-799
    A = "A"      # 600-699
    B = "B"      # 500-599: Revision manual
    C = "C"      # < 500: Rechazo automatico


class ProjectSector(str, enum.Enum):
    """Sectores de inversion."""
    INMOBILIARIO = "Inmobiliario"
    TECNOLOGIA = "Tecnologia"
    ENERGIA = "Energia"
    AGROTECH = "Agrotech"
    FINTECH = "Fintech"
    INDUSTRIAL = "Industrial"
    COMERCIO = "Comercio"
    SERVICIOS = "Servicios"
    INFRAESTRUCTURA = "Infraestructura"
    OTRO = "Otro"


class Project(Base):
    """
    Proyectos de inversion disponibles para financiamiento.
    """
    __tablename__ = "proyectos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=True)
    sector = Column(
        SQLEnum(ProjectSector, name="project_sector_enum"),
        default=ProjectSector.OTRO
    )

    # Montos financieros (NUMERIC para precision)
    monto_solicitado = Column(Numeric(18, 2), nullable=False)
    monto_financiado = Column(Numeric(18, 2), default=0)
    monto_minimo_inversion = Column(Numeric(18, 2), default=10000)

    # Plazos
    plazo_meses = Column(Integer, nullable=False)
    fecha_inicio_estimada = Column(DateTime(timezone=True), nullable=True)
    fecha_fin_estimada = Column(DateTime(timezone=True), nullable=True)

    # Estado
    estado = Column(
        SQLEnum(ProjectStatus, name="project_status_enum"),
        default=ProjectStatus.EN_EVALUACION
    )

    # Rendimientos ofrecidos
    tasa_rendimiento_anual = Column(Numeric(7, 4), nullable=True)  # Ej: 0.1500 = 15%
    rendimiento_proyectado = Column(Numeric(18, 2), nullable=True)

    # Solicitante
    solicitante_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    empresa_solicitante = Column(String(255), nullable=True)  # Nombre (legacy)

    # Empresa asociada (nueva relacion)
    empresa_id = Column(
        UUID(as_uuid=True),
        ForeignKey("empresas.id", ondelete="SET NULL"),
        nullable=True
    )

    # Documentacion
    tiene_documentacion_completa = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    # Relaciones
    evaluacion = relationship("FinancialEvaluation", back_populates="project", uselist=False)
    riesgo = relationship("RiskAnalysis", back_populates="project", uselist=False)
    flujos_caja = relationship("CashFlow", back_populates="project", order_by="CashFlow.periodo_nro")
    inversiones = relationship("Investment", back_populates="project")
    empresa = relationship("Company", back_populates="proyectos")

    __table_args__ = (
        Index("idx_proyecto_estado", "estado"),
        Index("idx_proyecto_sector", "sector"),
    )

    def __repr__(self):
        return f"<Project {self.nombre}>"


class FinancialEvaluation(Base):
    """
    Evaluacion financiera del proyecto.
    Calcula VAN, TIR, ROI, Payback automaticamente.
    """
    __tablename__ = "evaluaciones_financieras"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proyecto_id = Column(
        UUID(as_uuid=True),
        ForeignKey("proyectos.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    # Parametros de calculo
    inversion_inicial = Column(Numeric(18, 2), nullable=False)
    tasa_descuento_aplicada = Column(Numeric(7, 4), nullable=False)  # Ej: 0.1200 = 12%

    # Resultados (NUMERIC para precision financiera)
    van = Column(Numeric(18, 2), nullable=True)  # Valor Actual Neto
    tir = Column(Numeric(7, 4), nullable=True)   # Tasa Interna de Retorno
    roi = Column(Numeric(7, 4), nullable=True)   # Return on Investment
    payback_period = Column(Numeric(5, 2), nullable=True)  # Meses/Anos
    indice_rentabilidad = Column(Numeric(7, 4), nullable=True)  # PI = VAN / Inversion

    # Escenarios
    van_optimista = Column(Numeric(18, 2), nullable=True)
    van_pesimista = Column(Numeric(18, 2), nullable=True)
    tir_optimista = Column(Numeric(7, 4), nullable=True)
    tir_pesimista = Column(Numeric(7, 4), nullable=True)

    # Metadatos
    fecha_evaluacion = Column(DateTime(timezone=True), default=datetime.utcnow)
    evaluado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    notas = Column(Text, nullable=True)

    # Relaciones
    project = relationship("Project", back_populates="evaluacion")

    def __repr__(self):
        return f"<FinancialEvaluation VAN={self.van} TIR={self.tir}>"


class RiskAnalysis(Base):
    """
    Analisis de riesgo y Credit Scoring.
    Score de 0-1000 con categorizacion automatica.
    """
    __tablename__ = "analisis_riesgo"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proyecto_id = Column(
        UUID(as_uuid=True),
        ForeignKey("proyectos.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    # Credit Score (0-1000)
    score_crediticio = Column(
        Integer,
        CheckConstraint("score_crediticio BETWEEN 0 AND 1000"),
        nullable=True
    )

    # Nivel de riesgo derivado
    nivel_riesgo = Column(
        SQLEnum(RiskLevel, name="risk_level_enum"),
        nullable=True
    )

    # Probabilidades
    probabilidad_default = Column(Numeric(5, 4), nullable=True)  # 0.0000 - 1.0000
    probabilidad_exito = Column(Numeric(5, 4), nullable=True)

    # Componentes del Score (cada uno 0-1000)
    score_capacidad_pago = Column(Integer, nullable=True)     # C: 40%
    score_historial = Column(Integer, nullable=True)          # H: 35%
    score_garantias = Column(Integer, nullable=True)          # G: 25%

    # Ratios financieros
    ratio_deuda_ingreso = Column(Numeric(7, 4), nullable=True)  # D/I
    loan_to_value = Column(Numeric(7, 4), nullable=True)        # LTV

    # Garantias
    garantias_ofrecidas = Column(Text, nullable=True)
    valor_garantias = Column(Numeric(18, 2), nullable=True)

    # Analisis de sensibilidad (JSONB)
    analisis_sensibilidad = Column(JSONB, nullable=True)
    # Estructura: {"pesimista": {...}, "base": {...}, "optimista": {...}}

    # Comite
    comentarios_comite = Column(Text, nullable=True)
    aprobado_por_comite = Column(Boolean, nullable=True)
    fecha_revision_comite = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    # Relaciones
    project = relationship("Project", back_populates="riesgo")

    def __repr__(self):
        return f"<RiskAnalysis Score={self.score_crediticio} Level={self.nivel_riesgo}>"


class CashFlow(Base):
    """
    Flujos de caja proyectados.
    Base para calculos de VAN y TIR.
    """
    __tablename__ = "flujos_caja_proyectados"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proyecto_id = Column(
        UUID(as_uuid=True),
        ForeignKey("proyectos.id", ondelete="CASCADE"),
        nullable=False
    )

    # Periodo (mes o ano)
    periodo_nro = Column(Integer, nullable=False)
    periodo_tipo = Column(String(10), default="mes")  # mes o ano

    # Flujos
    monto_ingreso = Column(Numeric(18, 2), default=0)
    monto_egreso = Column(Numeric(18, 2), default=0)
    # flujo_neto se calcula en la aplicacion (ingreso - egreso)

    descripcion = Column(String(255), nullable=True)

    # Relaciones
    project = relationship("Project", back_populates="flujos_caja")

    __table_args__ = (
        Index("idx_flujo_proyecto_periodo", "proyecto_id", "periodo_nro"),
    )

    @property
    def flujo_neto(self) -> Decimal:
        """Calcula flujo neto."""
        return (self.monto_ingreso or Decimal(0)) - (self.monto_egreso or Decimal(0))

    def __repr__(self):
        return f"<CashFlow P{self.periodo_nro}: {self.flujo_neto}>"


class SectorIndicators(Base):
    """
    Indicadores especificos del sector para cada proyecto.
    Metricas clave dependientes del tipo de industria.
    """
    __tablename__ = "indicadores_sector"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proyecto_id = Column(
        UUID(as_uuid=True),
        ForeignKey("proyectos.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    # --- Indicadores de Tecnologia/SaaS ---
    ltv_cac_ratio = Column(Numeric(10, 4), nullable=True)       # Ratio LTV/CAC
    burn_rate = Column(Numeric(18, 2), nullable=True)           # Tasa de quema mensual
    runway_meses = Column(Integer, nullable=True)               # Runway en meses
    mrr = Column(Numeric(18, 2), nullable=True)                 # Monthly Recurring Revenue
    arr = Column(Numeric(18, 2), nullable=True)                 # Annual Recurring Revenue
    churn_rate = Column(Numeric(7, 4), nullable=True)           # Tasa de cancelacion
    nps = Column(Integer, nullable=True)                        # Net Promoter Score (-100 a 100)

    # --- Indicadores Inmobiliario ---
    cap_rate = Column(Numeric(7, 4), nullable=True)             # Tasa de capitalizacion
    precio_m2 = Column(Numeric(18, 2), nullable=True)           # Precio por metro cuadrado
    yield_bruto = Column(Numeric(7, 4), nullable=True)          # Rendimiento bruto anual
    yield_neto = Column(Numeric(7, 4), nullable=True)           # Rendimiento neto anual
    loan_to_value = Column(Numeric(7, 4), nullable=True)        # Relacion prestamo/valor
    debt_service_coverage = Column(Numeric(7, 4), nullable=True)  # DSCR

    # --- Indicadores Energia ---
    lcoe = Column(Numeric(18, 4), nullable=True)                # Levelized Cost of Energy
    factor_capacidad = Column(Numeric(7, 4), nullable=True)     # Factor de capacidad
    ingresos_kwh = Column(Numeric(10, 4), nullable=True)        # Ingresos por kWh
    costo_instalacion_kw = Column(Numeric(18, 2), nullable=True)  # Costo instalacion por kW
    vida_util_anos = Column(Integer, nullable=True)             # Vida util del proyecto

    # --- Indicadores Fintech ---
    take_rate = Column(Numeric(7, 4), nullable=True)            # Porcentaje comision transaccion
    volumen_procesado = Column(Numeric(18, 2), nullable=True)   # TPV mensual
    costo_adquisicion = Column(Numeric(18, 2), nullable=True)   # CAC
    lifetime_value = Column(Numeric(18, 2), nullable=True)      # LTV
    default_rate = Column(Numeric(7, 4), nullable=True)         # Tasa de incumplimiento

    # --- Indicadores Comercio/Industrial ---
    margen_bruto = Column(Numeric(7, 4), nullable=True)         # Margen bruto
    margen_operativo = Column(Numeric(7, 4), nullable=True)     # Margen operativo
    rotacion_inventario = Column(Numeric(7, 2), nullable=True)  # Veces que rota al ano
    ticket_promedio = Column(Numeric(18, 2), nullable=True)     # Valor promedio transaccion
    conversion_rate = Column(Numeric(7, 4), nullable=True)      # Tasa de conversion
    ventas_m2 = Column(Numeric(18, 2), nullable=True)           # Ventas por metro cuadrado
    utilizacion_capacidad = Column(Numeric(7, 4), nullable=True)  # % uso capacidad instalada
    costo_unitario = Column(Numeric(18, 4), nullable=True)      # Costo por unidad
    punto_equilibrio_unidades = Column(Integer, nullable=True)  # Unidades para break-even

    # --- Indicadores Agrotech ---
    rendimiento_hectarea = Column(Numeric(18, 4), nullable=True)  # Rendimiento por hectarea
    costo_produccion_ton = Column(Numeric(18, 2), nullable=True)  # Costo por tonelada
    punto_equilibrio = Column(Numeric(18, 2), nullable=True)      # Punto de equilibrio

    # --- Indicadores Infraestructura ---
    eirr = Column(Numeric(7, 4), nullable=True)                 # Economic IRR
    firr = Column(Numeric(7, 4), nullable=True)                 # Financial IRR
    beneficio_costo_ratio = Column(Numeric(7, 4), nullable=True)  # B/C Ratio
    trafico_proyectado = Column(Integer, nullable=True)         # Usuarios/vehiculos
    tarifa_promedio = Column(Numeric(18, 2), nullable=True)     # Tarifa promedio

    # --- Indicadores Servicios ---
    rotacion_clientes = Column(Numeric(7, 4), nullable=True)    # Tasa rotacion clientes

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    # Relacion
    project = relationship("Project", backref="indicadores_sector")

    def __repr__(self):
        return f"<SectorIndicators proyecto_id={self.proyecto_id}>"
