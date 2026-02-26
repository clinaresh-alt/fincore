"""
Endpoints para metricas sectoriales de proyectos.
CRUD de datos de entrada y calculo automatico de indicadores.
"""
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.project import Project
from app.models.sector_metrics import SectorMetrics, SECTOR_INPUT_FIELDS, SECTOR_CALCULATED_INDICATORS
from app.services.sector_indicators_engine import SectorIndicatorsEngine


router = APIRouter(prefix="/sector-metrics", tags=["Metricas Sectoriales"])


# ============ Schemas ============

class SectorInputData(BaseModel):
    """Datos de entrada para calcular indicadores sectoriales."""
    input_data: Dict[str, Any]


class SectorMetricsResponse(BaseModel):
    """Respuesta con metricas sectoriales."""
    id: Optional[UUID] = None
    proyecto_id: UUID
    sector: str
    input_data: Dict[str, Any]
    calculated_indicators: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    calculated_at: Optional[datetime] = None


class SectorFieldsResponse(BaseModel):
    """Respuesta con campos de entrada por sector."""
    sector: str
    fields: Dict[str, Any]
    calculated_indicators: list


# ============ Endpoints ============

@router.get("/sectors", response_model=list)
async def list_sectors(
    current_user: User = Depends(get_current_user)
):
    """
    Lista todos los sectores disponibles con sus campos.
    """
    return list(SECTOR_INPUT_FIELDS.keys())


@router.get("/sectors/{sector}/fields", response_model=SectorFieldsResponse)
async def get_sector_fields(
    sector: str,
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene los campos de entrada requeridos para un sector especifico.
    """
    sector_lower = sector.lower()

    if sector_lower not in SECTOR_INPUT_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sector '{sector}' no encontrado. Sectores disponibles: {list(SECTOR_INPUT_FIELDS.keys())}"
        )

    return SectorFieldsResponse(
        sector=sector_lower,
        fields=SECTOR_INPUT_FIELDS[sector_lower],
        calculated_indicators=SECTOR_CALCULATED_INDICATORS.get(sector_lower, [])
    )


@router.get("/projects/{proyecto_id}", response_model=SectorMetricsResponse)
async def get_project_sector_metrics(
    proyecto_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene las metricas sectoriales de un proyecto.
    """
    # Verificar que el proyecto existe
    proyecto = db.query(Project).filter(Project.id == proyecto_id).first()
    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado"
        )

    # Buscar metricas existentes
    metrics = db.query(SectorMetrics).filter(
        SectorMetrics.proyecto_id == proyecto_id
    ).first()

    if not metrics:
        # Retornar estructura vacia con campos del sector
        sector = proyecto.sector.lower() if proyecto.sector else "tecnologia"
        return SectorMetricsResponse(
            proyecto_id=proyecto_id,
            sector=sector,
            input_data={},
            calculated_indicators={}
        )

    return SectorMetricsResponse(
        id=metrics.id,
        proyecto_id=metrics.proyecto_id,
        sector=metrics.sector,
        input_data=metrics.input_data or {},
        calculated_indicators=metrics.calculated_indicators or {},
        created_at=metrics.created_at,
        updated_at=metrics.updated_at,
        calculated_at=metrics.calculated_at
    )


@router.post("/projects/{proyecto_id}", response_model=SectorMetricsResponse)
async def save_project_sector_metrics(
    proyecto_id: UUID,
    data: SectorInputData,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.ANALISTA])),
    db: Session = Depends(get_db)
):
    """
    Guarda datos sectoriales y calcula indicadores automaticamente.
    """
    # Verificar que el proyecto existe
    proyecto = db.query(Project).filter(Project.id == proyecto_id).first()
    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado"
        )

    sector = proyecto.sector.lower() if proyecto.sector else None
    if not sector or sector not in SECTOR_INPUT_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sector del proyecto no valido: {proyecto.sector}"
        )

    # Validar campos requeridos
    required_fields = [
        field for field, config in SECTOR_INPUT_FIELDS[sector].items()
        if config.get("required", False)
    ]

    missing_fields = []
    for field in required_fields:
        if field not in data.input_data or data.input_data[field] is None:
            missing_fields.append(field)

    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campos requeridos faltantes: {missing_fields}"
        )

    # Calcular indicadores
    engine = SectorIndicatorsEngine()
    calculated = engine.calculate(sector, data.input_data)

    # Buscar o crear registro
    metrics = db.query(SectorMetrics).filter(
        SectorMetrics.proyecto_id == proyecto_id
    ).first()

    now = datetime.utcnow()

    if metrics:
        # Actualizar existente
        metrics.input_data = data.input_data
        metrics.calculated_indicators = calculated
        metrics.updated_at = now
        metrics.calculated_at = now
    else:
        # Crear nuevo
        metrics = SectorMetrics(
            proyecto_id=proyecto_id,
            sector=sector,
            input_data=data.input_data,
            calculated_indicators=calculated,
            created_by=current_user.id,
            calculated_at=now
        )
        db.add(metrics)

    db.commit()
    db.refresh(metrics)

    return SectorMetricsResponse(
        id=metrics.id,
        proyecto_id=metrics.proyecto_id,
        sector=metrics.sector,
        input_data=metrics.input_data or {},
        calculated_indicators=metrics.calculated_indicators or {},
        created_at=metrics.created_at,
        updated_at=metrics.updated_at,
        calculated_at=metrics.calculated_at
    )


@router.post("/projects/{proyecto_id}/calculate", response_model=Dict[str, Any])
async def calculate_indicators_preview(
    proyecto_id: UUID,
    data: SectorInputData,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Calcula indicadores sin guardar (preview).
    Util para mostrar resultados antes de confirmar.
    """
    # Verificar que el proyecto existe
    proyecto = db.query(Project).filter(Project.id == proyecto_id).first()
    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado"
        )

    sector = proyecto.sector.lower() if proyecto.sector else None
    if not sector or sector not in SECTOR_INPUT_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sector del proyecto no valido: {proyecto.sector}"
        )

    # Calcular indicadores
    engine = SectorIndicatorsEngine()
    calculated = engine.calculate(sector, data.input_data)

    return {
        "sector": sector,
        "input_data": data.input_data,
        "calculated_indicators": calculated,
        "preview": True
    }


@router.delete("/projects/{proyecto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_sector_metrics(
    proyecto_id: UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Elimina las metricas sectoriales de un proyecto.
    Solo Admin puede eliminar.
    """
    metrics = db.query(SectorMetrics).filter(
        SectorMetrics.proyecto_id == proyecto_id
    ).first()

    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metricas sectoriales no encontradas para este proyecto"
        )

    db.delete(metrics)
    db.commit()
