"""
Modelo para metricas sectoriales de proyectos.
Almacena datos de entrada y calculos de indicadores por sector.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, String, Integer, DateTime, Text,
    ForeignKey, Numeric, Boolean
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class SectorMetrics(Base):
    """
    Metricas sectoriales para evaluacion de proyectos.
    Los datos de entrada varian segun el sector, se almacenan en JSONB.
    Los indicadores calculados tambien se almacenan en JSONB.
    """
    __tablename__ = "sector_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proyecto_id = Column(
        UUID(as_uuid=True),
        ForeignKey("proyectos.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    # Sector del proyecto (para validacion)
    sector = Column(String(50), nullable=False)

    # ====== DATOS DE ENTRADA POR SECTOR (JSONB flexible) ======
    # Tecnologia: usuarios_actuales, usuarios_proyectados, mrr, arr, cac, ltv, churn_mensual, gastos_mensuales, capital_disponible
    # Inmobiliario: metros_cuadrados, precio_m2, ocupacion_esperada, ingresos_renta_mensual, gastos_operativos, valor_propiedad, deuda_hipotecaria
    # Energia: capacidad_mw, factor_planta, precio_kwh, costo_instalacion_kw, vida_util_anos, produccion_anual_kwh
    # Fintech: volumen_transacciones, comision_promedio, usuarios_activos, tasa_default, costo_fondeo
    # Industrial: capacidad_produccion, produccion_actual, costo_unitario, precio_venta_unitario, inventario_promedio
    # Comercio: ventas_mensuales, metros_cuadrados, ticket_promedio, visitas_mensuales, inventario_promedio
    # Agrotech: hectareas, rendimiento_ton_ha, precio_ton, costo_produccion_ha, ciclos_por_ano
    # Infraestructura: usuarios_diarios, tarifa_promedio, costos_operativos_diarios, inversion_total, vida_util_anos

    input_data = Column(JSONB, nullable=False, default={})

    # ====== INDICADORES CALCULADOS (JSONB) ======
    # Cada sector tiene sus indicadores especificos calculados automaticamente
    calculated_indicators = Column(JSONB, nullable=False, default={})

    # Metadatos
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)
    calculated_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    def __repr__(self):
        return f"<SectorMetrics proyecto={self.proyecto_id} sector={self.sector}>"


# Definicion de campos de entrada por sector
SECTOR_INPUT_FIELDS = {
    "tecnologia": {
        "usuarios_actuales": {"label": "Usuarios Actuales", "type": "integer", "required": True},
        "usuarios_proyectados": {"label": "Usuarios Proyectados (12 meses)", "type": "integer", "required": False},
        "mrr": {"label": "MRR (Ingresos Recurrentes Mensuales)", "type": "decimal", "required": True},
        "cac": {"label": "CAC (Costo Adquisicion Cliente)", "type": "decimal", "required": True},
        "ltv": {"label": "LTV (Valor de Vida del Cliente)", "type": "decimal", "required": True},
        "churn_mensual": {"label": "Churn Rate Mensual (%)", "type": "percentage", "required": True},
        "gastos_mensuales": {"label": "Gastos Operativos Mensuales", "type": "decimal", "required": True},
        "capital_disponible": {"label": "Capital Disponible", "type": "decimal", "required": True},
        "arpu": {"label": "ARPU (Ingreso Promedio por Usuario)", "type": "decimal", "required": False},
        "nps_score": {"label": "NPS Score (-100 a 100)", "type": "integer", "required": False},
    },
    "inmobiliario": {
        "metros_cuadrados": {"label": "Metros Cuadrados Totales", "type": "decimal", "required": True},
        "precio_m2_venta": {"label": "Precio por M2 (Venta)", "type": "decimal", "required": False},
        "precio_m2_renta": {"label": "Precio por M2 (Renta Mensual)", "type": "decimal", "required": False},
        "ocupacion_actual": {"label": "Ocupacion Actual (%)", "type": "percentage", "required": True},
        "ocupacion_esperada": {"label": "Ocupacion Esperada (%)", "type": "percentage", "required": False},
        "ingresos_renta_mensual": {"label": "Ingresos Renta Mensual", "type": "decimal", "required": True},
        "gastos_operativos": {"label": "Gastos Operativos Mensuales", "type": "decimal", "required": True},
        "valor_propiedad": {"label": "Valor de la Propiedad", "type": "decimal", "required": True},
        "deuda_hipotecaria": {"label": "Deuda Hipotecaria", "type": "decimal", "required": False},
    },
    "energia": {
        "capacidad_mw": {"label": "Capacidad Instalada (MW)", "type": "decimal", "required": True},
        "factor_planta": {"label": "Factor de Planta (%)", "type": "percentage", "required": True},
        "precio_kwh": {"label": "Precio por kWh", "type": "decimal", "required": True},
        "costo_instalacion_kw": {"label": "Costo Instalacion por kW", "type": "decimal", "required": True},
        "costos_operativos_anuales": {"label": "Costos Operativos Anuales", "type": "decimal", "required": True},
        "vida_util_anos": {"label": "Vida Util (Anos)", "type": "integer", "required": True},
        "horas_operacion_dia": {"label": "Horas de Operacion por Dia", "type": "decimal", "required": False},
    },
    "fintech": {
        "volumen_transacciones_mensual": {"label": "Volumen Transacciones Mensual", "type": "decimal", "required": True},
        "comision_promedio": {"label": "Comision Promedio (%)", "type": "percentage", "required": True},
        "usuarios_activos": {"label": "Usuarios Activos Mensuales", "type": "integer", "required": True},
        "tasa_default": {"label": "Tasa de Default (%)", "type": "percentage", "required": True},
        "costo_fondeo": {"label": "Costo de Fondeo (%)", "type": "percentage", "required": False},
        "cartera_creditos": {"label": "Cartera de Creditos", "type": "decimal", "required": False},
        "cac": {"label": "CAC (Costo Adquisicion Cliente)", "type": "decimal", "required": True},
        "ltv": {"label": "LTV (Valor de Vida del Cliente)", "type": "decimal", "required": True},
    },
    "industrial": {
        "capacidad_produccion": {"label": "Capacidad de Produccion (unidades/mes)", "type": "decimal", "required": True},
        "produccion_actual": {"label": "Produccion Actual (unidades/mes)", "type": "decimal", "required": True},
        "costo_unitario": {"label": "Costo Unitario de Produccion", "type": "decimal", "required": True},
        "precio_venta_unitario": {"label": "Precio de Venta Unitario", "type": "decimal", "required": True},
        "costos_fijos_mensuales": {"label": "Costos Fijos Mensuales", "type": "decimal", "required": True},
        "inventario_promedio": {"label": "Inventario Promedio (unidades)", "type": "decimal", "required": False},
        "dias_cuentas_cobrar": {"label": "Dias Cuentas por Cobrar", "type": "integer", "required": False},
    },
    "comercio": {
        "ventas_mensuales": {"label": "Ventas Mensuales", "type": "decimal", "required": True},
        "metros_cuadrados": {"label": "Metros Cuadrados del Local", "type": "decimal", "required": True},
        "ticket_promedio": {"label": "Ticket Promedio", "type": "decimal", "required": True},
        "visitas_mensuales": {"label": "Visitas Mensuales", "type": "integer", "required": True},
        "costo_mercancia": {"label": "Costo de Mercancia (%)", "type": "percentage", "required": True},
        "gastos_operativos": {"label": "Gastos Operativos Mensuales", "type": "decimal", "required": True},
        "inventario_promedio": {"label": "Inventario Promedio", "type": "decimal", "required": False},
    },
    "agrotech": {
        "hectareas": {"label": "Hectareas", "type": "decimal", "required": True},
        "rendimiento_ton_ha": {"label": "Rendimiento (Ton/Ha)", "type": "decimal", "required": True},
        "precio_ton": {"label": "Precio por Tonelada", "type": "decimal", "required": True},
        "costo_produccion_ha": {"label": "Costo Produccion por Ha", "type": "decimal", "required": True},
        "ciclos_por_ano": {"label": "Ciclos de Cultivo por Ano", "type": "integer", "required": True},
        "hectareas_irrigadas": {"label": "Hectareas con Riego (%)", "type": "percentage", "required": False},
        "perdida_estimada": {"label": "Perdida Estimada (%)", "type": "percentage", "required": False},
    },
    "infraestructura": {
        "usuarios_diarios": {"label": "Usuarios/Vehiculos Diarios", "type": "integer", "required": True},
        "tarifa_promedio": {"label": "Tarifa Promedio", "type": "decimal", "required": True},
        "costos_operativos_mensuales": {"label": "Costos Operativos Mensuales", "type": "decimal", "required": True},
        "inversion_total": {"label": "Inversion Total del Proyecto", "type": "decimal", "required": True},
        "vida_util_anos": {"label": "Vida Util (Anos)", "type": "integer", "required": True},
        "crecimiento_trafico_anual": {"label": "Crecimiento Trafico Anual (%)", "type": "percentage", "required": False},
    },
}

# Indicadores que se calculan por sector
SECTOR_CALCULATED_INDICATORS = {
    "tecnologia": [
        "ltv_cac_ratio", "burn_rate", "runway_meses", "mrr", "arr",
        "churn_rate", "nps", "arpu", "crecimiento_usuarios"
    ],
    "inmobiliario": [
        "cap_rate", "precio_m2", "yield_bruto", "yield_neto",
        "loan_to_value", "noi", "ocupacion"
    ],
    "energia": [
        "lcoe", "factor_capacidad", "ingresos_kwh", "produccion_anual",
        "costo_instalacion_kw", "vida_util_anos", "roi_energia"
    ],
    "fintech": [
        "take_rate", "volumen_procesado", "ltv_cac_ratio", "default_rate",
        "spread", "cartera_neta"
    ],
    "industrial": [
        "margen_operativo", "utilizacion_capacidad", "costo_unitario",
        "punto_equilibrio_unidades", "margen_contribucion", "rotacion_inventario"
    ],
    "comercio": [
        "ventas_m2", "margen_bruto", "rotacion_inventario",
        "ticket_promedio", "conversion_rate", "punto_equilibrio"
    ],
    "agrotech": [
        "rendimiento_hectarea", "margen_bruto", "costo_produccion_ton",
        "punto_equilibrio", "ingreso_por_hectarea"
    ],
    "infraestructura": [
        "eirr", "firr", "beneficio_costo_ratio", "trafico_proyectado",
        "tarifa_promedio", "payback_infraestructura"
    ],
}
