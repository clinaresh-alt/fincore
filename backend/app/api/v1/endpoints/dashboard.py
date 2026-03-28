"""
API Endpoints para Dashboard de Monitoreo.

Proporciona:
- Métricas en tiempo real
- Estado del sistema
- Gestión de alertas
- WebSocket para actualizaciones
"""
from typing import List, Optional
from datetime import datetime, timedelta
import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session
from app.core.database import get_db

from app.services.metrics_service import get_metrics_service, MetricsService
from app.services.alert_service import get_alert_service, AlertService
from app.schemas.dashboard import (
    RemittanceMetrics,
    FinancialMetrics,
    QueueMetrics,
    SystemMetrics,
    SystemStatus,
    ServiceHealth,
    DashboardSnapshot,
    Alert,
    AlertRule,
    AlertSummary,
    AlertSeverity,
    AlertType,
    AlertStatus,
    TimeRange,
    CreateAlertRuleRequest,
    UpdateAlertRuleRequest,
    AcknowledgeAlertRequest,
    SilenceAlertRequest,
    WSMessage,
    WSMessageType,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ============ Response Models ============

class HealthResponse(BaseModel):
    """Respuesta de health check."""
    status: str
    timestamp: datetime
    version: str = "1.0.0"


class MetricsResponse(BaseModel):
    """Respuesta de métricas."""
    remittances: RemittanceMetrics
    financial: FinancialMetrics
    queue: QueueMetrics
    system: SystemMetrics


class AlertResponse(BaseModel):
    """Respuesta de alerta."""
    id: str
    type: str
    severity: str
    status: str
    title: str
    message: str
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class AlertRuleResponse(BaseModel):
    """Respuesta de regla de alerta."""
    id: str
    name: str
    type: str
    severity: str
    metric: str
    operator: str
    threshold: float
    enabled: bool


# ============ WebSocket Manager ============

class ConnectionManager:
    """Gestor de conexiones WebSocket."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Envía mensaje a todas las conexiones."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


# ============ Dashboard Endpoints ============

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check del dashboard."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
    )


@router.get("/snapshot")
async def get_dashboard_snapshot():
    """
    Obtiene snapshot completo del dashboard.

    Incluye todas las métricas, estado del sistema y alertas.
    """
    try:
        metrics_service = get_metrics_service()
        snapshot = await metrics_service.get_dashboard_snapshot()

        return {
            "timestamp": snapshot.timestamp.isoformat(),
            "remittances": snapshot.remittances.model_dump(),
            "financial": snapshot.financial.model_dump(),
            "queue": snapshot.queue.model_dump(),
            "system": snapshot.system.model_dump(),
            "status": {
                "overall": snapshot.status.overall_status.value,
                "services": {
                    "database": snapshot.status.services.database.status.value,
                    "redis": snapshot.status.services.redis.status.value,
                    "stp": snapshot.status.services.stp.status.value,
                    "bitso": snapshot.status.services.bitso.status.value,
                    "blockchain": snapshot.status.services.blockchain.status.value,
                },
                "active_alerts": snapshot.status.active_alerts,
            },
            "alerts": {
                "total_active": snapshot.alerts.total_active,
                "by_severity": snapshot.alerts.by_severity,
                "by_type": snapshot.alerts.by_type,
            },
            "recent_remittances": snapshot.recent_remittances,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Metrics Endpoints ============

@router.get("/metrics/remittances")
async def get_remittance_metrics():
    """Obtiene métricas de remesas."""
    try:
        metrics_service = get_metrics_service()
        metrics = await metrics_service.get_remittance_metrics()
        return metrics.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/financial")
async def get_financial_metrics():
    """Obtiene métricas financieras."""
    try:
        metrics_service = get_metrics_service()
        metrics = await metrics_service.get_financial_metrics()
        return metrics.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/queue")
async def get_queue_metrics():
    """Obtiene métricas de la cola de jobs."""
    try:
        metrics_service = get_metrics_service()
        metrics = await metrics_service.get_queue_metrics()
        return metrics.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/system")
async def get_system_metrics():
    """Obtiene métricas del sistema."""
    try:
        metrics_service = get_metrics_service()
        metrics = await metrics_service.get_system_metrics()
        return metrics.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Status Endpoints ============

@router.get("/status")
async def get_system_status():
    """Obtiene estado del sistema."""
    try:
        metrics_service = get_metrics_service()
        status = await metrics_service.get_system_status()

        return {
            "overall_status": status.overall_status.value,
            "is_healthy": status.is_healthy,
            "active_alerts": status.active_alerts,
            "services": {
                "database": {
                    "status": status.services.database.status.value,
                    "latency_ms": status.services.database.latency_ms,
                    "error": status.services.database.error_message,
                },
                "redis": {
                    "status": status.services.redis.status.value,
                    "latency_ms": status.services.redis.latency_ms,
                    "error": status.services.redis.error_message,
                },
                "stp": {
                    "status": status.services.stp.status.value,
                    "latency_ms": status.services.stp.latency_ms,
                    "error": status.services.stp.error_message,
                },
                "bitso": {
                    "status": status.services.bitso.status.value,
                    "latency_ms": status.services.bitso.latency_ms,
                    "error": status.services.bitso.error_message,
                },
                "blockchain": {
                    "status": status.services.blockchain.status.value,
                    "latency_ms": status.services.blockchain.latency_ms,
                    "error": status.services.blockchain.error_message,
                },
            },
            "last_updated": status.last_updated.isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/service/{service_name}")
async def get_service_status(service_name: str):
    """Obtiene estado de un servicio específico."""
    valid_services = ["database", "redis", "stp", "bitso", "blockchain"]

    if service_name not in valid_services:
        raise HTTPException(
            status_code=400,
            detail=f"Servicio inválido. Debe ser uno de: {valid_services}"
        )

    try:
        metrics_service = get_metrics_service()
        health = await metrics_service.check_service_health(service_name)

        return {
            "name": health.name,
            "status": health.status.value,
            "latency_ms": health.latency_ms,
            "error": health.error_message,
            "last_check": health.last_check.isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Alert Endpoints ============

@router.get("/alerts", response_model=List[AlertResponse])
async def list_alerts(
    status: Optional[str] = Query(None, description="Filtrar por status"),
    severity: Optional[str] = Query(None, description="Filtrar por severidad"),
    limit: int = Query(50, ge=1, le=200),
):
    """Lista alertas activas e históricas."""
    try:
        alert_service = get_alert_service()

        if status == "active":
            alerts = alert_service.get_active_alerts()
        else:
            alert_type = AlertType(severity) if severity else None
            alerts = alert_service.get_alert_history(
                limit=limit,
                severity=AlertSeverity(severity) if severity else None,
            )

        return [
            AlertResponse(
                id=a.id,
                type=a.type.value,
                severity=a.severity.value,
                status=a.status.value,
                title=a.title,
                message=a.message,
                triggered_at=a.triggered_at,
                acknowledged_at=a.acknowledged_at,
                resolved_at=a.resolved_at,
            )
            for a in alerts
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/summary")
async def get_alert_summary():
    """Obtiene resumen de alertas."""
    try:
        alert_service = get_alert_service()
        summary = alert_service.get_alert_summary()

        return {
            "total_active": summary.total_active,
            "by_severity": summary.by_severity,
            "by_type": summary.by_type,
            "recent": [
                {
                    "id": a.id,
                    "type": a.type.value,
                    "severity": a.severity.value,
                    "title": a.title,
                    "triggered_at": a.triggered_at.isoformat(),
                }
                for a in summary.recent_alerts
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/{alert_id}")
async def get_alert(alert_id: str):
    """Obtiene detalles de una alerta."""
    try:
        alert_service = get_alert_service()
        alerts = alert_service.get_alert_history(limit=1)

        # Buscar por ID
        for alert in alert_service.get_active_alerts():
            if alert.id == alert_id:
                return {
                    "id": alert.id,
                    "rule_id": alert.rule_id,
                    "type": alert.type.value,
                    "severity": alert.severity.value,
                    "status": alert.status.value,
                    "title": alert.title,
                    "message": alert.message,
                    "details": alert.details,
                    "metric_value": alert.metric_value,
                    "threshold": alert.threshold,
                    "triggered_at": alert.triggered_at.isoformat(),
                    "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                    "acknowledged_by": alert.acknowledged_by,
                    "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                    "remittance_id": alert.remittance_id,
                    "job_id": alert.job_id,
                }

        raise HTTPException(status_code=404, detail="Alerta no encontrada")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    request: AcknowledgeAlertRequest,
):
    """Marca una alerta como acknowledged."""
    try:
        alert_service = get_alert_service()
        success = await alert_service.acknowledge_alert(
            alert_id=alert_id,
            acknowledged_by=request.acknowledged_by,
            comment=request.comment,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")

        # Notificar via WebSocket
        await manager.broadcast({
            "type": WSMessageType.ALERT_RESOLVED.value,
            "data": {"alert_id": alert_id, "action": "acknowledged"},
        })

        return {"success": True, "message": "Alerta acknowledged"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """Resuelve una alerta."""
    try:
        alert_service = get_alert_service()
        success = await alert_service.resolve_alert(alert_id)

        if not success:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")

        await manager.broadcast({
            "type": WSMessageType.ALERT_RESOLVED.value,
            "data": {"alert_id": alert_id, "action": "resolved"},
        })

        return {"success": True, "message": "Alerta resuelta"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/silence")
async def silence_alert(
    alert_id: str,
    request: SilenceAlertRequest,
):
    """Silencia una alerta temporalmente."""
    try:
        alert_service = get_alert_service()
        success = await alert_service.silence_alert(
            alert_id=alert_id,
            duration_minutes=request.duration_minutes,
            reason=request.reason,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Alerta no encontrada")

        return {"success": True, "message": f"Alerta silenciada por {request.duration_minutes} minutos"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Alert Rules Endpoints ============

@router.get("/rules", response_model=List[AlertRuleResponse])
async def list_alert_rules():
    """Lista reglas de alerta."""
    try:
        alert_service = get_alert_service()
        rules = alert_service.get_rules()

        return [
            AlertRuleResponse(
                id=r.id,
                name=r.name,
                type=r.type.value,
                severity=r.severity.value,
                metric=r.metric,
                operator=r.operator,
                threshold=r.threshold,
                enabled=r.enabled,
            )
            for r in rules
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rules")
async def create_alert_rule(request: CreateAlertRuleRequest):
    """Crea una nueva regla de alerta."""
    try:
        alert_service = get_alert_service()

        rule = AlertRule(
            id="",  # Se asignará
            name=request.name,
            description=request.description,
            type=request.type,
            severity=request.severity,
            metric=request.metric,
            operator=request.operator,
            threshold=request.threshold,
            duration_seconds=request.duration_seconds,
            notify_channels=request.notify_channels,
        )

        rule_id = alert_service.create_rule(rule)

        return {"success": True, "rule_id": rule_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/rules/{rule_id}")
async def update_alert_rule(
    rule_id: str,
    request: UpdateAlertRuleRequest,
):
    """Actualiza una regla de alerta."""
    try:
        alert_service = get_alert_service()

        updates = request.model_dump(exclude_unset=True)
        success = alert_service.update_rule(rule_id, updates)

        if not success:
            raise HTTPException(status_code=404, detail="Regla no encontrada")

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(rule_id: str):
    """Elimina una regla de alerta."""
    try:
        alert_service = get_alert_service()
        success = alert_service.delete_rule(rule_id)

        if not success:
            raise HTTPException(status_code=404, detail="Regla no encontrada")

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ WebSocket Endpoint ============

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket para actualizaciones en tiempo real.

    Envía:
    - Actualizaciones de métricas cada 10 segundos
    - Alertas disparadas inmediatamente
    - Cambios de estado del sistema
    """
    await manager.connect(websocket)

    try:
        # Enviar snapshot inicial
        metrics_service = get_metrics_service()
        snapshot = await metrics_service.get_dashboard_snapshot()

        await websocket.send_json({
            "type": WSMessageType.METRICS_UPDATE.value,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "remittances": snapshot.remittances.model_dump(),
                "queue": snapshot.queue.model_dump(),
                "system": snapshot.system.model_dump(),
            },
        })

        # Loop de actualizaciones
        while True:
            try:
                # Esperar mensaje del cliente o timeout
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=10.0
                    )

                    # Procesar comandos del cliente
                    message = json.loads(data)
                    if message.get("type") == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.utcnow().isoformat(),
                        })

                except asyncio.TimeoutError:
                    # Enviar actualización de métricas
                    snapshot = await metrics_service.get_dashboard_snapshot()

                    await websocket.send_json({
                        "type": WSMessageType.METRICS_UPDATE.value,
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {
                            "remittances": {
                                "pending": snapshot.remittances.pending_count,
                                "processing": snapshot.remittances.processing_count,
                                "completed_today": snapshot.remittances.last_24h_count,
                                "success_rate": snapshot.remittances.success_rate,
                            },
                            "queue": {
                                "pending": snapshot.queue.pending_jobs,
                                "processing": snapshot.queue.processing_jobs,
                                "dead_letter": snapshot.queue.dead_letter_jobs,
                            },
                            "alerts": {
                                "active": snapshot.alerts.total_active,
                            },
                        },
                    })

            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(f"WebSocket error: {e}")

    finally:
        manager.disconnect(websocket)


# ============ Helper Functions ============

async def broadcast_alert(alert: Alert):
    """Broadcast una alerta a todos los clientes WebSocket."""
    await manager.broadcast({
        "type": WSMessageType.ALERT_TRIGGERED.value,
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "id": alert.id,
            "type": alert.type.value,
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
        },
    })
