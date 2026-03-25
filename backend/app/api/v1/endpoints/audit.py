"""
API Endpoints para Auditoría de Smart Contracts.

Expone funcionalidades de:
- Análisis estático con Slither
- Monitoreo de transacciones
- Gestión de incidentes
- Dashboard de seguridad
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.services.audit import (
    SlitherAuditService,
    TransactionMonitoringService,
    IncidentResponseService,
    AlertSeverity,
    IncidentSeverity,
)


router = APIRouter()

# Instancias de servicios (singleton por ahora)
_slither_service: Optional[SlitherAuditService] = None
_monitoring_service: Optional[TransactionMonitoringService] = None
_incident_service: Optional[IncidentResponseService] = None


def get_slither_service() -> SlitherAuditService:
    """Obtiene instancia del servicio Slither."""
    global _slither_service
    if _slither_service is None:
        _slither_service = SlitherAuditService()
    return _slither_service


def get_monitoring_service() -> TransactionMonitoringService:
    """Obtiene instancia del servicio de monitoreo."""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = TransactionMonitoringService()
    return _monitoring_service


def get_incident_service() -> IncidentResponseService:
    """Obtiene instancia del servicio IRP."""
    global _incident_service
    if _incident_service is None:
        _incident_service = IncidentResponseService(get_monitoring_service())
    return _incident_service


# ============ Schemas ============


class AuditContractRequest(BaseModel):
    """Request para auditar un contrato."""
    contract_path: str = Field(..., description="Ruta al archivo .sol")
    generate_html: bool = Field(default=True, description="Generar reporte HTML")


class AuditContractResponse(BaseModel):
    """Response de auditoría de contrato."""
    contract_path: str
    timestamp: datetime
    security_score: int
    vulnerabilities_count: dict[str, int]
    high_severity_issues: list[dict]
    recommendations: list[str]
    report_path: Optional[str] = None


class AnalyzeTransactionRequest(BaseModel):
    """Request para analizar una transacción."""
    tx_hash: str
    from_address: str
    to_address: str
    value: Decimal
    gas_price: int
    input_data: str = "0x"
    network: str = "ethereum"


class AlertResponse(BaseModel):
    """Response de alerta."""
    id: str
    type: str
    severity: str
    title: str
    description: str
    transaction_hash: Optional[str]
    contract_address: Optional[str]
    timestamp: datetime


class CreateIncidentRequest(BaseModel):
    """Request para crear un incidente."""
    title: str
    description: str
    severity: str = Field(..., pattern="^(sev1|sev2|sev3|sev4)$")
    affected_contracts: list[str] = []
    related_transactions: list[str] = []


class IncidentResponse(BaseModel):
    """Response de incidente."""
    id: str
    title: str
    description: str
    severity: str
    status: str
    detected_at: datetime
    contained_at: Optional[datetime]
    resolved_at: Optional[datetime]
    actions_count: int


class SecurityDashboardResponse(BaseModel):
    """Response del dashboard de seguridad."""
    alert_statistics: dict[str, Any]
    incident_statistics: dict[str, Any]
    active_incidents: list[dict]
    recent_alerts: list[dict]


# ============ Endpoints de Auditoría ============


@router.post("/contracts/audit", response_model=AuditContractResponse)
async def audit_contract(
    request: AuditContractRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Ejecuta análisis de seguridad Slither en un contrato.

    Requiere que Slither esté instalado en el sistema.
    El análisis puede tomar varios minutos dependiendo del tamaño del contrato.
    """
    slither = get_slither_service()

    if not slither.is_slither_installed():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slither no está instalado. Ejecute: pip install slither-analyzer",
        )

    try:
        result = await slither.audit_contract(
            contract_path=request.contract_path,
            generate_html=request.generate_html,
        )

        return AuditContractResponse(
            contract_path=result["contract_path"],
            timestamp=datetime.fromisoformat(result["timestamp"]),
            security_score=result["security_score"],
            vulnerabilities_count=result["vulnerabilities_count"],
            high_severity_issues=result["high_severity_issues"],
            recommendations=result["recommendations"],
            report_path=result.get("html_report_path"),
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato no encontrado: {request.contract_path}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante auditoría: {str(e)}",
        )


@router.get("/contracts/audit/detectors")
async def list_slither_detectors(
    current_user: User = Depends(get_current_user),
):
    """Lista todos los detectores disponibles en Slither."""
    slither = get_slither_service()
    return {"detectors": slither.list_detectors()}


# ============ Endpoints de Monitoreo ============


@router.post("/monitoring/analyze-transaction", response_model=list[AlertResponse])
async def analyze_transaction(
    request: AnalyzeTransactionRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Analiza una transacción para detectar actividad sospechosa.

    Evalúa contra todas las reglas de monitoreo configuradas
    y genera alertas si se detectan anomalías.
    """
    monitoring = get_monitoring_service()

    alerts = await monitoring.analyze_transaction(
        tx_hash=request.tx_hash,
        from_address=request.from_address,
        to_address=request.to_address,
        value=request.value,
        gas_price=request.gas_price,
        input_data=request.input_data,
        network=request.network,
    )

    return [
        AlertResponse(
            id=alert.id,
            type=alert.type.value,
            severity=alert.severity.value,
            title=alert.title,
            description=alert.description,
            transaction_hash=alert.transaction_hash,
            contract_address=alert.contract_address,
            timestamp=alert.timestamp,
        )
        for alert in alerts
    ]


@router.get("/monitoring/alerts", response_model=list[AlertResponse])
async def get_recent_alerts(
    limit: int = 50,
    severity: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Obtiene alertas recientes con filtros opcionales."""
    monitoring = get_monitoring_service()

    severity_enum = None
    if severity:
        try:
            severity_enum = AlertSeverity(severity)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Severidad inválida: {severity}",
            )

    alerts = monitoring.get_recent_alerts(limit=limit, severity=severity_enum)

    return [
        AlertResponse(
            id=alert.id,
            type=alert.type.value,
            severity=alert.severity.value,
            title=alert.title,
            description=alert.description,
            transaction_hash=alert.transaction_hash,
            contract_address=alert.contract_address,
            timestamp=alert.timestamp,
        )
        for alert in alerts
    ]


@router.post("/monitoring/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
):
    """Marca una alerta como reconocida."""
    monitoring = get_monitoring_service()

    if not monitoring.acknowledge_alert(alert_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alerta no encontrada: {alert_id}",
        )

    return {"status": "acknowledged", "alert_id": alert_id}


@router.get("/monitoring/statistics")
async def get_monitoring_statistics(
    current_user: User = Depends(get_current_user),
):
    """Obtiene estadísticas del sistema de monitoreo."""
    monitoring = get_monitoring_service()
    return monitoring.get_alert_statistics()


# ============ Endpoints de Incidentes ============


@router.post("/incidents", response_model=IncidentResponse)
async def create_incident(
    request: CreateIncidentRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Crea un nuevo incidente de seguridad.

    Los incidentes SEV1 activarán automáticamente el circuit breaker.
    """
    irp = get_incident_service()

    try:
        severity = IncidentSeverity(request.severity)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Severidad inválida: {request.severity}",
        )

    incident = await irp.create_incident(
        title=request.title,
        description=request.description,
        severity=severity,
        detected_by=current_user.email,
        affected_contracts=request.affected_contracts,
        related_transactions=request.related_transactions,
    )

    return IncidentResponse(
        id=incident.id,
        title=incident.title,
        description=incident.description,
        severity=incident.severity.value,
        status=incident.status.value,
        detected_at=incident.detected_at,
        contained_at=incident.contained_at,
        resolved_at=incident.resolved_at,
        actions_count=len(incident.actions_taken),
    )


@router.get("/incidents", response_model=list[IncidentResponse])
async def list_incidents(
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
):
    """Lista incidentes de seguridad."""
    irp = get_incident_service()

    if active_only:
        incidents = irp.get_active_incidents()
    else:
        incidents = list(irp.incidents.values())

    return [
        IncidentResponse(
            id=inc.id,
            title=inc.title,
            description=inc.description,
            severity=inc.severity.value,
            status=inc.status.value,
            detected_at=inc.detected_at,
            contained_at=inc.contained_at,
            resolved_at=inc.resolved_at,
            actions_count=len(inc.actions_taken),
        )
        for inc in incidents
    ]


@router.post("/incidents/{incident_id}/contain")
async def contain_incident(
    incident_id: str,
    current_user: User = Depends(get_current_user),
):
    """Contiene un incidente activando medidas de emergencia."""
    irp = get_incident_service()

    success = await irp.contain_incident(incident_id, current_user.email)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incidente no encontrado: {incident_id}",
        )

    return {"status": "contained", "incident_id": incident_id}


@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    root_cause: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Marca un incidente como resuelto."""
    irp = get_incident_service()

    success = await irp.resolve_incident(
        incident_id,
        current_user.email,
        root_cause,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incidente no encontrado: {incident_id}",
        )

    return {"status": "resolved", "incident_id": incident_id}


@router.get("/incidents/{incident_id}/postmortem")
async def get_incident_postmortem(
    incident_id: str,
    current_user: User = Depends(get_current_user),
):
    """Genera reporte post-mortem de un incidente."""
    irp = get_incident_service()
    report = irp.generate_postmortem_report(incident_id)

    if "error" in report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=report["error"],
        )

    return report


@router.get("/incidents/statistics")
async def get_incident_statistics(
    current_user: User = Depends(get_current_user),
):
    """Obtiene estadísticas de incidentes."""
    irp = get_incident_service()
    return irp.get_incident_statistics()


# ============ Dashboard de Seguridad ============


@router.get("/dashboard", response_model=SecurityDashboardResponse)
async def get_security_dashboard(
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene datos consolidados para el dashboard de seguridad.

    Incluye estadísticas de alertas, incidentes y estado general.
    """
    monitoring = get_monitoring_service()
    irp = get_incident_service()

    # Obtener incidentes activos
    active_incidents = irp.get_active_incidents()
    active_incidents_data = [
        {
            "id": inc.id,
            "title": inc.title,
            "severity": inc.severity.value,
            "status": inc.status.value,
            "detected_at": inc.detected_at.isoformat(),
        }
        for inc in active_incidents[:10]  # Top 10
    ]

    # Obtener alertas recientes
    recent_alerts = monitoring.get_recent_alerts(limit=20)
    recent_alerts_data = [
        {
            "id": alert.id,
            "type": alert.type.value,
            "severity": alert.severity.value,
            "title": alert.title,
            "timestamp": alert.timestamp.isoformat(),
        }
        for alert in recent_alerts
    ]

    return SecurityDashboardResponse(
        alert_statistics=monitoring.get_alert_statistics(),
        incident_statistics=irp.get_incident_statistics(),
        active_incidents=active_incidents_data,
        recent_alerts=recent_alerts_data,
    )
