"""
Endpoints de Reconciliacion para FinCore.

API REST para:
- Ejecutar reconciliacion manual
- Consultar historial de reconciliaciones
- Resolver discrepancias
- Monitorear estado del scheduler
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User, UserRole
from app.models.remittance import ReconciliationLog
from app.services.reconciliation_service import (
    ReconciliationService,
    ReconciliationResult,
    TransactionReconciliation,
    DiscrepancyType,
    AlertSeverity,
)


router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


# ============ Schemas ============

class ReconciliationSummary(BaseModel):
    """Resumen de una reconciliacion."""
    id: str
    timestamp: datetime
    discrepancy_detected: bool
    discrepancy_amount: float
    network: str
    stablecoin: str
    resolved: bool
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReconciliationDetail(BaseModel):
    """Detalle completo de reconciliacion."""
    id: str
    check_timestamp: datetime
    expected_balance_ledger: float
    actual_balance_ledger: float
    expected_balance_onchain: float
    actual_balance_onchain: float
    discrepancy_ledger: float
    discrepancy_onchain: float
    discrepancy_detected: bool
    network: str
    stablecoin: str
    contract_address: Optional[str]
    error_payload: Optional[dict]
    action_taken: Optional[str]
    resolved: bool
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]

    class Config:
        from_attributes = True


class RunReconciliationRequest(BaseModel):
    """Request para ejecutar reconciliacion."""
    stablecoin: str = Field(default="USDC", pattern="^(USDC|USDT|DAI)$")


class RunReconciliationResponse(BaseModel):
    """Response de reconciliacion ejecutada."""
    success: bool
    timestamp: datetime
    log_id: Optional[str] = None
    discrepancies_count: int = 0
    alerts_sent: int = 0
    error: Optional[str] = None


class ResolveDiscrepancyRequest(BaseModel):
    """Request para resolver discrepancia."""
    action_taken: str = Field(..., min_length=10, max_length=1000)


class ReconcileSingleRequest(BaseModel):
    """Request para reconciliar remesa individual."""
    remittance_id: str


class ReconcileSingleResponse(BaseModel):
    """Response de reconciliacion individual."""
    remittance_id: str
    reference_code: str
    ledger_status: str
    onchain_status: Optional[str]
    ledger_amount: float
    onchain_amount: Optional[float]
    is_matched: bool
    discrepancy_type: Optional[str]
    details: Optional[str]


class SchedulerStatusResponse(BaseModel):
    """Estado del scheduler."""
    status: str
    timezone: Optional[str] = None
    jobs: List[dict] = []


# ============ Helpers ============

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Requiere que el usuario sea admin."""
    if current_user.rol != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador"
        )
    return current_user


def require_operator_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """Requiere que el usuario sea operador o admin."""
    if current_user.rol not in [UserRole.ADMIN, UserRole.ANALISTA]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de operador o administrador"
        )
    return current_user


# ============ Endpoints ============

@router.post(
    "/run",
    response_model=RunReconciliationResponse,
    summary="Ejecutar reconciliacion manual",
    description="Ejecuta una reconciliacion completa entre Ledger y On-chain"
)
async def run_reconciliation(
    request: RunReconciliationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Ejecuta reconciliacion manual."""
    service = ReconciliationService(db=db)

    result = await service.run_full_reconciliation(stablecoin=request.stablecoin)

    return RunReconciliationResponse(
        success=result.success,
        timestamp=result.timestamp,
        log_id=result.log_id,
        discrepancies_count=len(result.discrepancies),
        alerts_sent=result.alerts_sent,
        error=result.error,
    )


@router.get(
    "/history",
    response_model=List[ReconciliationSummary],
    summary="Historial de reconciliaciones",
    description="Obtiene el historial de reconciliaciones ejecutadas"
)
async def get_reconciliation_history(
    limit: int = Query(default=50, ge=1, le=500),
    only_discrepancies: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
):
    """Obtiene historial de reconciliaciones."""
    service = ReconciliationService(db=db)
    logs = service.get_reconciliation_history(
        limit=limit,
        only_discrepancies=only_discrepancies
    )

    return [
        ReconciliationSummary(
            id=str(log.id),
            timestamp=log.check_timestamp,
            discrepancy_detected=log.discrepancy_detected,
            discrepancy_amount=float(log.discrepancy_onchain or 0),
            network=log.network,
            stablecoin=log.stablecoin,
            resolved=log.resolved,
            resolved_at=log.resolved_at,
        )
        for log in logs
    ]


@router.get(
    "/unresolved",
    response_model=List[ReconciliationDetail],
    summary="Discrepancias no resueltas",
    description="Obtiene lista de discrepancias pendientes de resolver"
)
async def get_unresolved_discrepancies(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
):
    """Obtiene discrepancias no resueltas."""
    service = ReconciliationService(db=db)
    logs = service.get_unresolved_discrepancies()

    return [
        ReconciliationDetail(
            id=str(log.id),
            check_timestamp=log.check_timestamp,
            expected_balance_ledger=float(log.expected_balance_ledger),
            actual_balance_ledger=float(log.actual_balance_ledger),
            expected_balance_onchain=float(log.expected_balance_onchain),
            actual_balance_onchain=float(log.actual_balance_onchain),
            discrepancy_ledger=float(log.discrepancy_ledger or 0),
            discrepancy_onchain=float(log.discrepancy_onchain or 0),
            discrepancy_detected=log.discrepancy_detected,
            network=log.network,
            stablecoin=log.stablecoin,
            contract_address=log.contract_address,
            error_payload=log.error_payload,
            action_taken=log.action_taken,
            resolved=log.resolved,
            resolved_at=log.resolved_at,
            resolved_by=str(log.resolved_by) if log.resolved_by else None,
        )
        for log in logs
    ]


@router.get(
    "/{log_id}",
    response_model=ReconciliationDetail,
    summary="Detalle de reconciliacion",
    description="Obtiene detalles de una reconciliacion especifica"
)
async def get_reconciliation_detail(
    log_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
):
    """Obtiene detalle de una reconciliacion."""
    log = db.query(ReconciliationLog).filter(
        ReconciliationLog.id == log_id
    ).first()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de reconciliacion no encontrado"
        )

    return ReconciliationDetail(
        id=str(log.id),
        check_timestamp=log.check_timestamp,
        expected_balance_ledger=float(log.expected_balance_ledger),
        actual_balance_ledger=float(log.actual_balance_ledger),
        expected_balance_onchain=float(log.expected_balance_onchain),
        actual_balance_onchain=float(log.actual_balance_onchain),
        discrepancy_ledger=float(log.discrepancy_ledger or 0),
        discrepancy_onchain=float(log.discrepancy_onchain or 0),
        discrepancy_detected=log.discrepancy_detected,
        network=log.network,
        stablecoin=log.stablecoin,
        contract_address=log.contract_address,
        error_payload=log.error_payload,
        action_taken=log.action_taken,
        resolved=log.resolved,
        resolved_at=log.resolved_at,
        resolved_by=str(log.resolved_by) if log.resolved_by else None,
    )


@router.post(
    "/{log_id}/resolve",
    summary="Resolver discrepancia",
    description="Marca una discrepancia como resuelta"
)
async def resolve_discrepancy(
    log_id: str,
    request: ResolveDiscrepancyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Resuelve una discrepancia."""
    service = ReconciliationService(db=db)

    success = service.resolve_discrepancy(
        log_id=log_id,
        resolved_by=str(current_user.id),
        action_taken=request.action_taken,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro de reconciliacion no encontrado"
        )

    return {"success": True, "message": "Discrepancia resuelta"}


@router.post(
    "/reconcile-single",
    response_model=ReconcileSingleResponse,
    summary="Reconciliar remesa individual",
    description="Reconcilia una remesa especifica contra on-chain"
)
async def reconcile_single_remittance(
    request: ReconcileSingleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
):
    """Reconcilia una remesa individual."""
    service = ReconciliationService(db=db)

    result = await service.reconcile_single_remittance(request.remittance_id)

    return ReconcileSingleResponse(
        remittance_id=result.remittance_id,
        reference_code=result.reference_code,
        ledger_status=result.ledger_status,
        onchain_status=result.onchain_status,
        ledger_amount=float(result.ledger_amount),
        onchain_amount=float(result.onchain_amount) if result.onchain_amount else None,
        is_matched=result.is_matched,
        discrepancy_type=result.discrepancy_type.value if result.discrepancy_type else None,
        details=result.details,
    )


@router.get(
    "/scheduler/status",
    response_model=SchedulerStatusResponse,
    summary="Estado del scheduler",
    description="Obtiene el estado actual del scheduler de jobs"
)
async def get_scheduler_status(
    current_user: User = Depends(require_admin),
):
    """Obtiene estado del scheduler."""
    from app.core.scheduler import get_scheduler_status
    return get_scheduler_status()


@router.post(
    "/scheduler/run/{job_id}",
    summary="Ejecutar job manualmente",
    description="Ejecuta un job del scheduler inmediatamente"
)
async def run_scheduler_job(
    job_id: str,
    current_user: User = Depends(require_admin),
):
    """Ejecuta un job del scheduler manualmente."""
    from app.core.scheduler import run_job_now

    success = await run_job_now(job_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' no encontrado o scheduler no activo"
        )

    return {"success": True, "message": f"Job '{job_id}' ejecutado"}


@router.get(
    "/stats/summary",
    summary="Resumen de estadisticas",
    description="Obtiene resumen de estadisticas de reconciliacion"
)
async def get_reconciliation_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
):
    """Obtiene estadisticas de reconciliacion."""
    from sqlalchemy import func
    from datetime import timedelta

    # Total de reconciliaciones
    total_logs = db.query(func.count(ReconciliationLog.id)).scalar()

    # Con discrepancias
    with_discrepancies = db.query(func.count(ReconciliationLog.id)).filter(
        ReconciliationLog.discrepancy_detected == True
    ).scalar()

    # Resueltas
    resolved = db.query(func.count(ReconciliationLog.id)).filter(
        ReconciliationLog.resolved == True
    ).scalar()

    # Ultima reconciliacion
    last_log = db.query(ReconciliationLog).order_by(
        ReconciliationLog.check_timestamp.desc()
    ).first()

    # Ultimas 24h
    last_24h = db.query(func.count(ReconciliationLog.id)).filter(
        ReconciliationLog.check_timestamp >= datetime.utcnow() - timedelta(hours=24)
    ).scalar()

    return {
        "total_reconciliations": total_logs,
        "with_discrepancies": with_discrepancies,
        "resolved": resolved,
        "pending": with_discrepancies - resolved,
        "last_24h": last_24h,
        "last_reconciliation": last_log.check_timestamp.isoformat() if last_log else None,
        "last_had_discrepancy": last_log.discrepancy_detected if last_log else None,
    }
