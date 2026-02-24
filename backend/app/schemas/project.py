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


class ProjectResponse(BaseModel):
    """Respuesta con datos de proyecto."""
    id: UUID
    nombre: str
    descripcion: Optional[str]
    sector: str
    monto_solicitado: Decimal
    monto_financiado: Decimal
    plazo_meses: int
    estado: str
    tasa_rendimiento_anual: Optional[Decimal]
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
