"""
Schemas de Proyectos y Evaluacion Financiera.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from uuid import UUID


class CashFlowInput(BaseModel):
    """Flujo de caja por periodo."""
    periodo_nro: int = Field(..., ge=1)
    monto_ingreso: Decimal = Field(default=Decimal("0"))
    monto_egreso: Decimal = Field(default=Decimal("0"))
    descripcion: Optional[str] = None


class ProjectCreate(BaseModel):
    """Schema para crear proyecto."""
    nombre: str = Field(..., min_length=3, max_length=255)
    descripcion: Optional[str] = None
    sector: str = Field(default="Otro")
    monto_solicitado: Decimal = Field(..., gt=0)
    plazo_meses: int = Field(..., ge=1, le=360)
    tasa_rendimiento_anual: Optional[Decimal] = Field(None, ge=0, le=1)
    empresa_solicitante: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "nombre": "Desarrollo Inmobiliario Plaza Central",
                "descripcion": "Construccion de centro comercial",
                "sector": "Inmobiliario",
                "monto_solicitado": 5000000.00,
                "plazo_meses": 24,
                "tasa_rendimiento_anual": 0.15
            }
        }


class ProjectUpdate(BaseModel):
    """Schema para actualizar proyecto."""
    nombre: Optional[str] = Field(None, min_length=3, max_length=255)
    descripcion: Optional[str] = None
    sector: Optional[str] = None
    monto_solicitado: Optional[Decimal] = Field(None, gt=0)
    monto_minimo_inversion: Optional[Decimal] = Field(None, gt=0)
    plazo_meses: Optional[int] = Field(None, ge=1, le=360)
    fecha_inicio_estimada: Optional[datetime] = None
    fecha_fin_estimada: Optional[datetime] = None
    tasa_rendimiento_anual: Optional[Decimal] = Field(None, ge=0, le=1)
    rendimiento_proyectado: Optional[Decimal] = None
    empresa_solicitante: Optional[str] = None
    tiene_documentacion_completa: Optional[bool] = None

    class Config:
        json_schema_extra = {
            "example": {
                "nombre": "Nuevo nombre del proyecto",
                "descripcion": "Nueva descripcion",
                "monto_solicitado": 6000000.00,
                "monto_minimo_inversion": 10000.00,
                "rendimiento_proyectado": 750000.00
            }
        }


class ProjectResponse(BaseModel):
    """Respuesta con datos de proyecto."""
    id: UUID
    nombre: str
    descripcion: Optional[str]
    sector: str
    monto_solicitado: Decimal
    monto_financiado: Decimal
    monto_minimo_inversion: Optional[Decimal] = None
    plazo_meses: int
    fecha_inicio_estimada: Optional[datetime] = None
    fecha_fin_estimada: Optional[datetime] = None
    estado: str
    tasa_rendimiento_anual: Optional[Decimal]
    rendimiento_proyectado: Optional[Decimal] = None
    empresa_solicitante: Optional[str] = None
    tiene_documentacion_completa: Optional[bool] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectEvaluate(BaseModel):
    """Request para evaluar proyecto financieramente."""
    proyecto_id: UUID
    inversion_inicial: Decimal = Field(..., gt=0)
    tasa_descuento: Decimal = Field(..., ge=0, le=1)
    flujos_caja: List[CashFlowInput]

    # Datos para analisis de riesgo
    ingresos_mensuales_solicitante: Optional[Decimal] = None
    gastos_fijos_solicitante: Optional[Decimal] = None
    deuda_actual_solicitante: Optional[Decimal] = None
    meses_actividad: Optional[int] = None
    pagos_puntuales: Optional[int] = None
    pagos_atrasados: Optional[int] = None
    valor_garantias: Optional[Decimal] = None
    tipo_garantia: Optional[str] = "ninguna"

    class Config:
        json_schema_extra = {
            "example": {
                "proyecto_id": "uuid-ejemplo",
                "inversion_inicial": 1000000,
                "tasa_descuento": 0.12,
                "flujos_caja": [
                    {"periodo_nro": 1, "monto_ingreso": 150000, "monto_egreso": 50000},
                    {"periodo_nro": 2, "monto_ingreso": 180000, "monto_egreso": 50000},
                    {"periodo_nro": 3, "monto_ingreso": 200000, "monto_egreso": 50000}
                ],
                "ingresos_mensuales_solicitante": 500000,
                "valor_garantias": 2000000,
                "tipo_garantia": "inmueble"
            }
        }


class EvaluationResponse(BaseModel):
    """Respuesta de evaluacion financiera."""
    proyecto_id: UUID
    inversion_inicial: Decimal
    tasa_descuento: Decimal

    # Indicadores
    van: Decimal
    tir: Optional[Decimal]
    roi: Decimal
    payback_period: Optional[Decimal]
    indice_rentabilidad: Decimal

    # Escenarios
    escenarios: Optional[List[dict]] = None

    # Viabilidad
    es_viable: bool
    mensaje: str
    fecha_evaluacion: datetime


class RiskAnalysisResponse(BaseModel):
    """Respuesta de analisis de riesgo."""
    proyecto_id: UUID

    # Score
    score_total: int
    score_capacidad_pago: int
    score_historial: int
    score_garantias: int

    # Nivel y accion
    nivel_riesgo: str
    accion_recomendada: str

    # Probabilidades
    probabilidad_default: Decimal
    probabilidad_exito: Decimal

    # Ratios
    ratio_deuda_ingreso: Optional[Decimal]
    loan_to_value: Optional[Decimal]

    # Recomendaciones
    tasa_interes_sugerida: Decimal
    monto_maximo_aprobado: Optional[Decimal]
    requiere_garantias_adicionales: bool
    observaciones: List[str]


class ProjectAnalyticsResponse(BaseModel):
    """
    Respuesta completa de analiticas del proyecto.
    Para el portal del inversionista.
    """
    project_id: UUID
    nombre: str
    estado: str

    financials: dict  # van, tir, roi, risk_level
    cash_flow_series: List[dict]  # [{period, amount}]

    # Progreso de financiamiento
    monto_solicitado: Decimal
    monto_financiado: Decimal
    porcentaje_financiado: Decimal

    # Inversionistas
    total_inversionistas: int


class SectorIndicatorsBase(BaseModel):
    """Schema base para indicadores del sector."""
    # --- Tecnologia/SaaS ---
    ltv_cac_ratio: Optional[Decimal] = None
    burn_rate: Optional[Decimal] = None
    runway_meses: Optional[int] = None
    mrr: Optional[Decimal] = None
    arr: Optional[Decimal] = None
    churn_rate: Optional[Decimal] = None
    nps: Optional[int] = None

    # --- Inmobiliario ---
    cap_rate: Optional[Decimal] = None
    precio_m2: Optional[Decimal] = None
    yield_bruto: Optional[Decimal] = None
    yield_neto: Optional[Decimal] = None
    loan_to_value: Optional[Decimal] = None
    debt_service_coverage: Optional[Decimal] = None

    # --- Energia ---
    lcoe: Optional[Decimal] = None
    factor_capacidad: Optional[Decimal] = None
    ingresos_kwh: Optional[Decimal] = None
    costo_instalacion_kw: Optional[Decimal] = None
    vida_util_anos: Optional[int] = None

    # --- Fintech ---
    take_rate: Optional[Decimal] = None
    volumen_procesado: Optional[Decimal] = None
    costo_adquisicion: Optional[Decimal] = None
    lifetime_value: Optional[Decimal] = None
    default_rate: Optional[Decimal] = None

    # --- Comercio/Industrial ---
    margen_bruto: Optional[Decimal] = None
    margen_operativo: Optional[Decimal] = None
    rotacion_inventario: Optional[Decimal] = None
    ticket_promedio: Optional[Decimal] = None
    conversion_rate: Optional[Decimal] = None
    ventas_m2: Optional[Decimal] = None
    utilizacion_capacidad: Optional[Decimal] = None
    costo_unitario: Optional[Decimal] = None
    punto_equilibrio_unidades: Optional[int] = None

    # --- Agrotech ---
    rendimiento_hectarea: Optional[Decimal] = None
    costo_produccion_ton: Optional[Decimal] = None
    punto_equilibrio: Optional[Decimal] = None

    # --- Infraestructura ---
    eirr: Optional[Decimal] = None
    firr: Optional[Decimal] = None
    beneficio_costo_ratio: Optional[Decimal] = None
    trafico_proyectado: Optional[int] = None
    tarifa_promedio: Optional[Decimal] = None

    # --- Servicios ---
    rotacion_clientes: Optional[Decimal] = None


class SectorIndicatorsCreate(SectorIndicatorsBase):
    """Schema para crear indicadores del sector."""
    proyecto_id: UUID


class SectorIndicatorsUpdate(SectorIndicatorsBase):
    """Schema para actualizar indicadores del sector."""
    pass


class SectorIndicatorsResponse(SectorIndicatorsBase):
    """Respuesta con indicadores del sector."""
    id: UUID
    proyecto_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
