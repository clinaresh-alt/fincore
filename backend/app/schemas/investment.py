"""
Schemas de Inversiones y Portfolio.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from uuid import UUID


class InvestmentCreate(BaseModel):
    """Schema para crear inversion."""
    proyecto_id: UUID
    monto: Decimal = Field(..., gt=0)
    metodo_pago: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "proyecto_id": "uuid-proyecto",
                "monto": 100000.00,
                "metodo_pago": "transferencia"
            }
        }


class InvestmentResponse(BaseModel):
    """Respuesta con datos de inversion."""
    id: UUID
    proyecto_id: UUID
    proyecto_nombre: Optional[str] = None
    monto_invertido: Decimal
    monto_rendimiento_acumulado: Decimal
    monto_total_recibido: Decimal
    porcentaje_participacion: Optional[Decimal]
    estado: str
    fecha_inversion: datetime
    fecha_vencimiento: Optional[datetime]

    class Config:
        from_attributes = True


class TransactionResponse(BaseModel):
    """Respuesta de transaccion."""
    id: UUID
    tipo: str
    monto: Decimal
    concepto: Optional[str]
    fecha_transaccion: datetime


class InvestmentDetailResponse(BaseModel):
    """Detalle completo de inversion."""
    inversion: InvestmentResponse
    proyecto: dict  # Datos basicos del proyecto
    transacciones: List[TransactionResponse]
    rendimiento_porcentual: Decimal


# === PORTFOLIO (Dashboard Inversionista) ===

class PortfolioKPIs(BaseModel):
    """KPIs del portfolio del inversionista."""
    total_invertido: Decimal
    rendimiento_total: Decimal
    rendimiento_porcentual: Decimal  # ROI global
    tir_cartera: Optional[Decimal]   # TIR ponderada
    moic: Decimal  # Multiple on Invested Capital

    # Conteos
    proyectos_activos: int
    proyectos_completados: int
    proyectos_en_default: int


class DistribucionSector(BaseModel):
    """Distribucion por sector."""
    sector: str
    monto: Decimal
    porcentaje: Decimal
    cantidad_proyectos: int


class ProximoPago(BaseModel):
    """Proximo pago esperado."""
    proyecto_id: UUID
    proyecto_nombre: str
    tipo: str  # interes, capital, dividendo
    monto_esperado: Decimal
    fecha_esperada: datetime


class PortfolioResponse(BaseModel):
    """
    Respuesta completa del portfolio.
    Dashboard principal del inversionista.
    """
    # Resumen
    kpis: PortfolioKPIs

    # Diversificacion
    distribucion_sectores: List[DistribucionSector]

    # Inversiones activas
    inversiones: List[InvestmentResponse]

    # Calendario de pagos
    proximos_pagos: List[ProximoPago]

    # Historico
    rendimiento_historico: List[dict]  # [{mes, rendimiento}]

    class Config:
        json_schema_extra = {
            "example": {
                "kpis": {
                    "total_invertido": 500000,
                    "rendimiento_total": 75000,
                    "rendimiento_porcentual": 0.15,
                    "tir_cartera": 0.12,
                    "moic": 1.15,
                    "proyectos_activos": 3,
                    "proyectos_completados": 2,
                    "proyectos_en_default": 0
                },
                "distribucion_sectores": [
                    {"sector": "Inmobiliario", "monto": 200000, "porcentaje": 0.40, "cantidad_proyectos": 2},
                    {"sector": "Tecnologia", "monto": 300000, "porcentaje": 0.60, "cantidad_proyectos": 1}
                ]
            }
        }
