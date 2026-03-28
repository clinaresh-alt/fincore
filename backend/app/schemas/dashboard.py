"""
Schemas para Dashboard de Monitoreo y Alertas.

Define modelos para:
- Métricas en tiempo real
- Alertas configurables
- Estado del sistema
- Notificaciones
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from enum import Enum


# ============ Enums ============

class AlertSeverity(str, Enum):
    """Severidad de alertas."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Tipos de alertas."""
    # Sistema
    SYSTEM_DOWN = "system.down"
    SYSTEM_DEGRADED = "system.degraded"
    HIGH_LATENCY = "high_latency"

    # Remesas
    REMITTANCE_STUCK = "remittance.stuck"
    REMITTANCE_FAILED = "remittance.failed"
    HIGH_FAILURE_RATE = "high_failure_rate"

    # Financiero
    LOW_BALANCE = "low_balance"
    HIGH_VOLUME = "high_volume"
    RATE_DEVIATION = "rate_deviation"

    # Reconciliación
    RECONCILIATION_DISCREPANCY = "reconciliation.discrepancy"

    # Compliance
    COMPLIANCE_ALERT = "compliance.alert"
    SCREENING_FAILED = "screening.failed"

    # Integraciones
    STP_UNREACHABLE = "stp.unreachable"
    BITSO_UNREACHABLE = "bitso.unreachable"
    BLOCKCHAIN_CONGESTION = "blockchain.congestion"

    # Cola de jobs
    QUEUE_BACKLOG = "queue.backlog"
    DEAD_LETTER_HIGH = "dead_letter.high"
    WORKER_DOWN = "worker.down"


class AlertStatus(str, Enum):
    """Estado de alertas."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SILENCED = "silenced"


class MetricType(str, Enum):
    """Tipos de métricas."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class TimeRange(str, Enum):
    """Rangos de tiempo para métricas."""
    LAST_HOUR = "1h"
    LAST_6_HOURS = "6h"
    LAST_24_HOURS = "24h"
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"


class ServiceStatus(str, Enum):
    """Estado de servicios."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


# ============ Métricas ============

class MetricValue(BaseModel):
    """Valor de una métrica en un punto de tiempo."""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = Field(default_factory=dict)


class MetricSeries(BaseModel):
    """Serie temporal de una métrica."""
    name: str
    type: MetricType
    description: Optional[str] = None
    unit: Optional[str] = None
    values: List[MetricValue] = Field(default_factory=list)

    @property
    def latest(self) -> Optional[float]:
        """Obtiene el valor más reciente."""
        if self.values:
            return self.values[-1].value
        return None

    @property
    def average(self) -> Optional[float]:
        """Calcula el promedio."""
        if self.values:
            return sum(v.value for v in self.values) / len(self.values)
        return None


class RemittanceMetrics(BaseModel):
    """Métricas de remesas."""
    total_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    pending_count: int = 0
    processing_count: int = 0

    total_volume_usdc: Decimal = Decimal("0")
    total_volume_mxn: Decimal = Decimal("0")

    avg_processing_time_seconds: float = 0
    success_rate: float = 0

    # Por período
    last_hour_count: int = 0
    last_24h_count: int = 0
    last_7d_count: int = 0


class FinancialMetrics(BaseModel):
    """Métricas financieras."""
    # Balances
    usdc_balance: Decimal = Decimal("0")
    mxn_balance: Decimal = Decimal("0")

    # Liquidez
    usdc_available: Decimal = Decimal("0")
    mxn_available: Decimal = Decimal("0")

    # Volumen
    daily_volume_usdc: Decimal = Decimal("0")
    daily_volume_mxn: Decimal = Decimal("0")

    # Tasas
    current_rate_usdc_mxn: Decimal = Decimal("0")
    rate_change_24h: float = 0  # Porcentaje

    # Fees
    total_fees_collected: Decimal = Decimal("0")
    avg_fee_percentage: float = 0


class QueueMetrics(BaseModel):
    """Métricas de la cola de jobs."""
    pending_jobs: int = 0
    processing_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    dead_letter_jobs: int = 0

    avg_wait_time_seconds: float = 0
    avg_processing_time_seconds: float = 0

    jobs_per_minute: float = 0
    error_rate: float = 0

    active_workers: int = 0

    # Por tipo
    jobs_by_type: Dict[str, int] = Field(default_factory=dict)


class SystemMetrics(BaseModel):
    """Métricas del sistema."""
    cpu_usage: float = 0
    memory_usage: float = 0
    disk_usage: float = 0

    active_connections: int = 0
    requests_per_second: float = 0
    avg_response_time_ms: float = 0
    error_rate: float = 0

    uptime_seconds: int = 0


# ============ Estado de Servicios ============

class ServiceHealth(BaseModel):
    """Estado de salud de un servicio."""
    name: str
    status: ServiceStatus
    latency_ms: Optional[float] = None
    last_check: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class IntegrationStatus(BaseModel):
    """Estado de integraciones externas."""
    stp: ServiceHealth
    bitso: ServiceHealth
    blockchain: ServiceHealth
    redis: ServiceHealth
    database: ServiceHealth
    chainalysis: Optional[ServiceHealth] = None


class SystemStatus(BaseModel):
    """Estado general del sistema."""
    overall_status: ServiceStatus
    services: IntegrationStatus
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    active_alerts: int = 0

    @property
    def is_healthy(self) -> bool:
        return self.overall_status == ServiceStatus.HEALTHY


# ============ Alertas ============

class AlertRule(BaseModel):
    """Regla de alerta configurable."""
    id: str
    name: str
    description: Optional[str] = None
    type: AlertType
    severity: AlertSeverity

    # Condiciones
    metric: str  # Nombre de la métrica a monitorear
    operator: str  # gt, lt, eq, gte, lte
    threshold: float
    duration_seconds: int = 60  # Tiempo que debe cumplirse la condición

    # Notificaciones
    notify_channels: List[str] = Field(default_factory=list)  # email, slack, webhook
    notify_interval_minutes: int = 15  # No repetir antes de X minutos

    # Estado
    enabled: bool = True
    silenced_until: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Alert(BaseModel):
    """Alerta activa o histórica."""
    id: str
    rule_id: str
    type: AlertType
    severity: AlertSeverity
    status: AlertStatus

    title: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)

    # Contexto
    metric_value: Optional[float] = None
    threshold: Optional[float] = None

    # Timestamps
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    # Referencias
    remittance_id: Optional[str] = None
    job_id: Optional[str] = None


class AlertSummary(BaseModel):
    """Resumen de alertas."""
    total_active: int = 0
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
    recent_alerts: List[Alert] = Field(default_factory=list)


# ============ Dashboard ============

class DashboardWidget(BaseModel):
    """Widget de dashboard."""
    id: str
    type: str  # metric_card, chart, table, status, alert_list
    title: str
    position: Dict[str, int]  # x, y, width, height
    config: Dict[str, Any] = Field(default_factory=dict)


class DashboardConfig(BaseModel):
    """Configuración de dashboard."""
    id: str
    name: str
    description: Optional[str] = None
    widgets: List[DashboardWidget] = Field(default_factory=list)
    refresh_interval_seconds: int = 30
    is_default: bool = False
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DashboardSnapshot(BaseModel):
    """Snapshot completo del dashboard."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Métricas
    remittances: RemittanceMetrics
    financial: FinancialMetrics
    queue: QueueMetrics
    system: SystemMetrics

    # Estado
    status: SystemStatus
    alerts: AlertSummary

    # Actividad reciente
    recent_remittances: List[Dict[str, Any]] = Field(default_factory=list)
    recent_events: List[Dict[str, Any]] = Field(default_factory=list)


# ============ Notificaciones ============

class NotificationChannel(str, Enum):
    """Canales de notificación."""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"
    PUSH = "push"


class NotificationConfig(BaseModel):
    """Configuración de canal de notificación."""
    channel: NotificationChannel
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)

    # Para email
    email_recipients: List[str] = Field(default_factory=list)

    # Para Slack
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None

    # Para webhook genérico
    webhook_url: Optional[str] = None
    webhook_headers: Dict[str, str] = Field(default_factory=dict)


class Notification(BaseModel):
    """Notificación enviada."""
    id: str
    alert_id: str
    channel: NotificationChannel
    recipient: str
    subject: str
    body: str
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    delivered: bool = False
    error: Optional[str] = None


# ============ Request/Response Models ============

class CreateAlertRuleRequest(BaseModel):
    """Request para crear regla de alerta."""
    name: str
    type: AlertType
    severity: AlertSeverity
    metric: str
    operator: str
    threshold: float
    duration_seconds: int = 60
    notify_channels: List[str] = Field(default_factory=list)
    description: Optional[str] = None

    @field_validator('operator')
    @classmethod
    def validate_operator(cls, v):
        valid = ['gt', 'lt', 'eq', 'gte', 'lte']
        if v not in valid:
            raise ValueError(f'Operator must be one of: {valid}')
        return v


class UpdateAlertRuleRequest(BaseModel):
    """Request para actualizar regla de alerta."""
    name: Optional[str] = None
    severity: Optional[AlertSeverity] = None
    threshold: Optional[float] = None
    enabled: Optional[bool] = None
    notify_channels: Optional[List[str]] = None


class AcknowledgeAlertRequest(BaseModel):
    """Request para acknowledger alerta."""
    acknowledged_by: str
    comment: Optional[str] = None


class SilenceAlertRequest(BaseModel):
    """Request para silenciar alerta."""
    duration_minutes: int = Field(ge=5, le=1440)  # 5 min a 24 horas
    reason: Optional[str] = None


class MetricsQueryRequest(BaseModel):
    """Request para consultar métricas."""
    metrics: List[str]
    time_range: TimeRange = TimeRange.LAST_HOUR
    resolution: Optional[str] = None  # 1m, 5m, 1h, etc.
    labels: Dict[str, str] = Field(default_factory=dict)


class MetricsQueryResponse(BaseModel):
    """Response de consulta de métricas."""
    time_range: TimeRange
    start_time: datetime
    end_time: datetime
    series: List[MetricSeries]


# ============ WebSocket Messages ============

class WSMessageType(str, Enum):
    """Tipos de mensajes WebSocket."""
    METRICS_UPDATE = "metrics_update"
    ALERT_TRIGGERED = "alert_triggered"
    ALERT_RESOLVED = "alert_resolved"
    STATUS_CHANGE = "status_change"
    REMITTANCE_UPDATE = "remittance_update"
    HEARTBEAT = "heartbeat"


class WSMessage(BaseModel):
    """Mensaje WebSocket."""
    type: WSMessageType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any]


# ============ Constantes ============

# Umbrales por defecto para alertas
DEFAULT_THRESHOLDS = {
    "low_balance_usdc": 1000,  # USDC
    "low_balance_mxn": 50000,  # MXN
    "high_failure_rate": 0.1,  # 10%
    "high_latency_ms": 5000,  # 5 segundos
    "queue_backlog": 100,  # jobs
    "dead_letter_high": 10,  # jobs
    "rate_deviation_percent": 5,  # 5%
}

# Intervalos de refresco por defecto
DEFAULT_REFRESH_INTERVALS = {
    "metrics": 10,  # segundos
    "status": 30,  # segundos
    "alerts": 5,  # segundos
}
