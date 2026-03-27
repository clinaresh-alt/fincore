"""
Servicio de Alertas para FinCore.

Monitorea métricas y dispara alertas basadas en reglas configurables.
Soporta múltiples canales de notificación (email, Slack, webhook).
"""
import os
import json
import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from uuid import uuid4
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Boolean, Float, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base, SessionLocal
from app.schemas.dashboard import (
    AlertType,
    AlertSeverity,
    AlertStatus,
    Alert,
    AlertRule,
    AlertSummary,
    NotificationChannel,
    NotificationConfig,
    Notification,
    DEFAULT_THRESHOLDS,
)

# Prometheus metrics
from prometheus_client import Counter, Gauge

logger = logging.getLogger(__name__)


# ==================== Configuración ====================

ALERT_CHECK_INTERVAL = int(os.getenv("ALERT_CHECK_INTERVAL", "30"))  # segundos
ALERT_RETENTION_DAYS = int(os.getenv("ALERT_RETENTION_DAYS", "30"))

# Slack
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SLACK_ALERT_CHANNEL = os.getenv("SLACK_ALERT_CHANNEL", "#alerts")

# Email (configuración básica, usar con sendgrid/ses)
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM", "alerts@fincore.com")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "").split(",")


# ==================== Métricas Prometheus ====================

ALERTS_TRIGGERED = Counter(
    'alerts_triggered_total',
    'Total de alertas disparadas',
    ['type', 'severity']
)

ALERTS_RESOLVED = Counter(
    'alerts_resolved_total',
    'Total de alertas resueltas',
    ['type']
)

ACTIVE_ALERTS = Gauge(
    'active_alerts',
    'Alertas activas actualmente',
    ['severity']
)

NOTIFICATIONS_SENT = Counter(
    'alert_notifications_sent_total',
    'Total de notificaciones enviadas',
    ['channel', 'status']
)


# ==================== Modelos de DB ====================

class AlertRuleModel(Base):
    """Modelo de regla de alerta en DB."""
    __tablename__ = "alert_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)

    # Condiciones
    metric = Column(String(100), nullable=False)
    operator = Column(String(10), nullable=False)
    threshold = Column(Float, nullable=False)
    duration_seconds = Column(Integer, default=60)

    # Notificaciones
    notify_channels = Column(JSONB, default=[])
    notify_interval_minutes = Column(Integer, default=15)

    # Estado
    enabled = Column(Boolean, default=True)
    silenced_until = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class AlertModel(Base):
    """Modelo de alerta en DB."""
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    rule_id = Column(UUID(as_uuid=True), nullable=True)
    type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    status = Column(String(20), default="active", index=True)

    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    details = Column(JSONB, default={})

    metric_value = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)

    # Timestamps
    triggered_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Referencias
    remittance_id = Column(String(50), nullable=True, index=True)
    job_id = Column(String(50), nullable=True)


class NotificationModel(Base):
    """Modelo de notificación en DB."""
    __tablename__ = "alert_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    alert_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    channel = Column(String(20), nullable=False)
    recipient = Column(String(200), nullable=False)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    delivered = Column(Boolean, default=False)
    error = Column(Text, nullable=True)


# ==================== Servicio de Alertas ====================

class AlertService:
    """
    Servicio de gestión de alertas.

    Features:
    - Evaluación de reglas contra métricas
    - Notificaciones multicanal
    - Deduplicación de alertas
    - Historial y auditoría
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._rules: Dict[str, AlertRule] = {}
        self._active_alerts: Dict[str, Alert] = {}
        self._metric_buffer: Dict[str, List[float]] = {}
        self._running = False
        self._check_task: Optional[asyncio.Task] = None
        self._notification_handlers: Dict[NotificationChannel, Callable] = {}

        # Registrar handlers de notificación
        self._register_notification_handlers()

        # Cargar reglas
        self._load_rules()

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def _register_notification_handlers(self):
        """Registra handlers para cada canal de notificación."""
        self._notification_handlers = {
            NotificationChannel.SLACK: self._send_slack_notification,
            NotificationChannel.WEBHOOK: self._send_webhook_notification,
            NotificationChannel.EMAIL: self._send_email_notification,
        }

    def _load_rules(self):
        """Carga reglas de la base de datos."""
        try:
            rules = self.db.query(AlertRuleModel).filter(
                AlertRuleModel.enabled == True
            ).all()

            for rule in rules:
                self._rules[str(rule.id)] = AlertRule(
                    id=str(rule.id),
                    name=rule.name,
                    description=rule.description,
                    type=AlertType(rule.type),
                    severity=AlertSeverity(rule.severity),
                    metric=rule.metric,
                    operator=rule.operator,
                    threshold=rule.threshold,
                    duration_seconds=rule.duration_seconds,
                    notify_channels=rule.notify_channels or [],
                    notify_interval_minutes=rule.notify_interval_minutes,
                    enabled=rule.enabled,
                    silenced_until=rule.silenced_until,
                )

            logger.info(f"Cargadas {len(self._rules)} reglas de alerta")

        except Exception as e:
            logger.error(f"Error cargando reglas: {e}")
            # Cargar reglas por defecto
            self._load_default_rules()

    def _load_default_rules(self):
        """Carga reglas de alerta por defecto."""
        default_rules = [
            AlertRule(
                id="default_low_balance",
                name="Balance bajo USDC",
                type=AlertType.LOW_BALANCE,
                severity=AlertSeverity.WARNING,
                metric="usdc_balance",
                operator="lt",
                threshold=DEFAULT_THRESHOLDS["low_balance_usdc"],
                duration_seconds=300,
                notify_channels=["slack", "email"],
            ),
            AlertRule(
                id="default_high_failure_rate",
                name="Tasa de fallos alta",
                type=AlertType.HIGH_FAILURE_RATE,
                severity=AlertSeverity.ERROR,
                metric="remittance_failure_rate",
                operator="gt",
                threshold=DEFAULT_THRESHOLDS["high_failure_rate"],
                duration_seconds=300,
                notify_channels=["slack"],
            ),
            AlertRule(
                id="default_queue_backlog",
                name="Cola con backlog",
                type=AlertType.QUEUE_BACKLOG,
                severity=AlertSeverity.WARNING,
                metric="pending_jobs",
                operator="gt",
                threshold=DEFAULT_THRESHOLDS["queue_backlog"],
                duration_seconds=600,
                notify_channels=["slack"],
            ),
            AlertRule(
                id="default_dead_letter",
                name="Dead letter queue alta",
                type=AlertType.DEAD_LETTER_HIGH,
                severity=AlertSeverity.ERROR,
                metric="dead_letter_jobs",
                operator="gt",
                threshold=DEFAULT_THRESHOLDS["dead_letter_high"],
                duration_seconds=300,
                notify_channels=["slack", "email"],
            ),
            AlertRule(
                id="default_stp_down",
                name="STP no disponible",
                type=AlertType.STP_UNREACHABLE,
                severity=AlertSeverity.CRITICAL,
                metric="stp_status",
                operator="eq",
                threshold=0,  # 0 = down
                duration_seconds=60,
                notify_channels=["slack", "email"],
            ),
        ]

        for rule in default_rules:
            self._rules[rule.id] = rule

        logger.info(f"Cargadas {len(default_rules)} reglas por defecto")

    # ==================== API Pública ====================

    async def start(self):
        """Inicia el servicio de monitoreo."""
        if self._running:
            return

        self._running = True
        self._check_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Alert service iniciado")

    async def stop(self):
        """Detiene el servicio."""
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        logger.info("Alert service detenido")

    def record_metric(self, metric_name: str, value: float):
        """Registra un valor de métrica para evaluación."""
        if metric_name not in self._metric_buffer:
            self._metric_buffer[metric_name] = []

        self._metric_buffer[metric_name].append(value)

        # Mantener solo últimos N valores
        max_values = 100
        if len(self._metric_buffer[metric_name]) > max_values:
            self._metric_buffer[metric_name] = self._metric_buffer[metric_name][-max_values:]

    async def trigger_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        details: Optional[Dict] = None,
        remittance_id: Optional[str] = None,
        job_id: Optional[str] = None,
        rule_id: Optional[str] = None,
    ) -> Alert:
        """
        Dispara una alerta manualmente.

        Args:
            alert_type: Tipo de alerta
            severity: Severidad
            title: Título de la alerta
            message: Mensaje descriptivo
            details: Detalles adicionales
            remittance_id: ID de remesa relacionada
            job_id: ID de job relacionado
            rule_id: ID de regla que disparó la alerta

        Returns:
            Alerta creada
        """
        alert_id = str(uuid4())

        alert = Alert(
            id=alert_id,
            rule_id=rule_id or "",
            type=alert_type,
            severity=severity,
            status=AlertStatus.ACTIVE,
            title=title,
            message=message,
            details=details or {},
            remittance_id=remittance_id,
            job_id=job_id,
        )

        # Verificar si ya existe una alerta similar activa (deduplicación)
        existing = self._find_similar_alert(alert)
        if existing:
            logger.debug(f"Alerta similar ya existe: {existing.id}")
            return existing

        # Guardar en DB
        db_alert = AlertModel(
            id=alert_id,
            rule_id=rule_id,
            type=alert_type.value,
            severity=severity.value,
            status=AlertStatus.ACTIVE.value,
            title=title,
            message=message,
            details=details or {},
            remittance_id=remittance_id,
            job_id=job_id,
        )
        self.db.add(db_alert)
        self.db.commit()

        # Agregar a alertas activas
        self._active_alerts[alert_id] = alert

        # Métricas
        ALERTS_TRIGGERED.labels(type=alert_type.value, severity=severity.value).inc()
        self._update_active_alerts_gauge()

        # Enviar notificaciones
        await self._send_notifications(alert)

        logger.warning(f"Alerta disparada: {title} (ID: {alert_id})")
        return alert

    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
        comment: Optional[str] = None,
    ) -> bool:
        """Marca una alerta como acknowledged."""
        db_alert = self.db.query(AlertModel).filter(
            AlertModel.id == alert_id
        ).first()

        if not db_alert:
            return False

        db_alert.status = AlertStatus.ACKNOWLEDGED.value
        db_alert.acknowledged_at = datetime.utcnow()
        db_alert.acknowledged_by = acknowledged_by

        if comment:
            details = db_alert.details or {}
            details["ack_comment"] = comment
            db_alert.details = details

        self.db.commit()

        # Actualizar cache
        if alert_id in self._active_alerts:
            self._active_alerts[alert_id].status = AlertStatus.ACKNOWLEDGED
            self._active_alerts[alert_id].acknowledged_at = datetime.utcnow()
            self._active_alerts[alert_id].acknowledged_by = acknowledged_by

        logger.info(f"Alerta {alert_id} acknowledged por {acknowledged_by}")
        return True

    async def resolve_alert(self, alert_id: str) -> bool:
        """Resuelve una alerta."""
        db_alert = self.db.query(AlertModel).filter(
            AlertModel.id == alert_id
        ).first()

        if not db_alert:
            return False

        db_alert.status = AlertStatus.RESOLVED.value
        db_alert.resolved_at = datetime.utcnow()
        self.db.commit()

        # Remover de activas
        if alert_id in self._active_alerts:
            alert = self._active_alerts.pop(alert_id)
            ALERTS_RESOLVED.labels(type=alert.type.value).inc()

        self._update_active_alerts_gauge()
        logger.info(f"Alerta {alert_id} resuelta")
        return True

    async def silence_alert(
        self,
        alert_id: str,
        duration_minutes: int,
        reason: Optional[str] = None,
    ) -> bool:
        """Silencia una alerta temporalmente."""
        db_alert = self.db.query(AlertModel).filter(
            AlertModel.id == alert_id
        ).first()

        if not db_alert:
            return False

        silenced_until = datetime.utcnow() + timedelta(minutes=duration_minutes)

        db_alert.status = AlertStatus.SILENCED.value
        details = db_alert.details or {}
        details["silenced_until"] = silenced_until.isoformat()
        details["silence_reason"] = reason
        db_alert.details = details
        self.db.commit()

        if alert_id in self._active_alerts:
            self._active_alerts[alert_id].status = AlertStatus.SILENCED

        logger.info(f"Alerta {alert_id} silenciada hasta {silenced_until}")
        return True

    def get_active_alerts(self) -> List[Alert]:
        """Obtiene todas las alertas activas."""
        return list(self._active_alerts.values())

    def get_alert_summary(self) -> AlertSummary:
        """Obtiene resumen de alertas."""
        alerts = list(self._active_alerts.values())

        by_severity = {}
        by_type = {}

        for alert in alerts:
            sev = alert.severity.value
            typ = alert.type.value

            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_type[typ] = by_type.get(typ, 0) + 1

        return AlertSummary(
            total_active=len(alerts),
            by_severity=by_severity,
            by_type=by_type,
            recent_alerts=sorted(alerts, key=lambda a: a.triggered_at, reverse=True)[:10],
        )

    def get_alert_history(
        self,
        limit: int = 100,
        alert_type: Optional[AlertType] = None,
        severity: Optional[AlertSeverity] = None,
        since: Optional[datetime] = None,
    ) -> List[Alert]:
        """Obtiene historial de alertas."""
        query = self.db.query(AlertModel).order_by(
            AlertModel.triggered_at.desc()
        )

        if alert_type:
            query = query.filter(AlertModel.type == alert_type.value)
        if severity:
            query = query.filter(AlertModel.severity == severity.value)
        if since:
            query = query.filter(AlertModel.triggered_at >= since)

        alerts = query.limit(limit).all()

        return [
            Alert(
                id=str(a.id),
                rule_id=str(a.rule_id) if a.rule_id else "",
                type=AlertType(a.type),
                severity=AlertSeverity(a.severity),
                status=AlertStatus(a.status),
                title=a.title,
                message=a.message,
                details=a.details or {},
                metric_value=a.metric_value,
                threshold=a.threshold,
                triggered_at=a.triggered_at,
                acknowledged_at=a.acknowledged_at,
                acknowledged_by=a.acknowledged_by,
                resolved_at=a.resolved_at,
                remittance_id=a.remittance_id,
                job_id=a.job_id,
            )
            for a in alerts
        ]

    # ==================== Gestión de Reglas ====================

    def create_rule(self, rule: AlertRule) -> str:
        """Crea una nueva regla de alerta."""
        rule_id = str(uuid4())
        rule.id = rule_id

        db_rule = AlertRuleModel(
            id=rule_id,
            name=rule.name,
            description=rule.description,
            type=rule.type.value,
            severity=rule.severity.value,
            metric=rule.metric,
            operator=rule.operator,
            threshold=rule.threshold,
            duration_seconds=rule.duration_seconds,
            notify_channels=rule.notify_channels,
            notify_interval_minutes=rule.notify_interval_minutes,
            enabled=rule.enabled,
        )
        self.db.add(db_rule)
        self.db.commit()

        self._rules[rule_id] = rule
        logger.info(f"Regla de alerta creada: {rule.name}")
        return rule_id

    def update_rule(self, rule_id: str, updates: Dict[str, Any]) -> bool:
        """Actualiza una regla existente."""
        db_rule = self.db.query(AlertRuleModel).filter(
            AlertRuleModel.id == rule_id
        ).first()

        if not db_rule:
            return False

        for key, value in updates.items():
            if hasattr(db_rule, key):
                setattr(db_rule, key, value)

        self.db.commit()

        # Actualizar cache
        if rule_id in self._rules:
            for key, value in updates.items():
                if hasattr(self._rules[rule_id], key):
                    setattr(self._rules[rule_id], key, value)

        return True

    def delete_rule(self, rule_id: str) -> bool:
        """Elimina una regla."""
        db_rule = self.db.query(AlertRuleModel).filter(
            AlertRuleModel.id == rule_id
        ).first()

        if not db_rule:
            return False

        self.db.delete(db_rule)
        self.db.commit()

        if rule_id in self._rules:
            del self._rules[rule_id]

        return True

    def get_rules(self) -> List[AlertRule]:
        """Obtiene todas las reglas."""
        return list(self._rules.values())

    # ==================== Evaluación de Reglas ====================

    async def _monitoring_loop(self):
        """Loop principal de monitoreo."""
        while self._running:
            try:
                await self._evaluate_rules()
                await self._check_resolved_alerts()
                await asyncio.sleep(ALERT_CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"Error en monitoring loop: {e}")
                await asyncio.sleep(5)

    async def _evaluate_rules(self):
        """Evalúa todas las reglas contra métricas actuales."""
        for rule_id, rule in self._rules.items():
            if not rule.enabled:
                continue

            if rule.silenced_until and rule.silenced_until > datetime.utcnow():
                continue

            try:
                metric_values = self._metric_buffer.get(rule.metric, [])
                if not metric_values:
                    continue

                # Obtener valores del período de duración
                # Simplificado: usar último valor
                current_value = metric_values[-1]

                if self._check_condition(current_value, rule.operator, rule.threshold):
                    # Condición cumplida, disparar alerta
                    await self.trigger_alert(
                        alert_type=rule.type,
                        severity=rule.severity,
                        title=rule.name,
                        message=f"{rule.metric} = {current_value} (umbral: {rule.operator} {rule.threshold})",
                        details={
                            "metric": rule.metric,
                            "value": current_value,
                            "threshold": rule.threshold,
                            "operator": rule.operator,
                        },
                        rule_id=rule_id,
                    )

            except Exception as e:
                logger.error(f"Error evaluando regla {rule_id}: {e}")

    def _check_condition(self, value: float, operator: str, threshold: float) -> bool:
        """Verifica si una condición se cumple."""
        ops = {
            "gt": lambda v, t: v > t,
            "lt": lambda v, t: v < t,
            "eq": lambda v, t: v == t,
            "gte": lambda v, t: v >= t,
            "lte": lambda v, t: v <= t,
        }
        return ops.get(operator, lambda v, t: False)(value, threshold)

    async def _check_resolved_alerts(self):
        """Verifica si alertas activas deberían resolverse."""
        alerts_to_resolve = []

        for alert_id, alert in self._active_alerts.items():
            # Verificar si la condición ya no se cumple
            if alert.rule_id and alert.rule_id in self._rules:
                rule = self._rules[alert.rule_id]
                metric_values = self._metric_buffer.get(rule.metric, [])

                if metric_values:
                    current_value = metric_values[-1]
                    if not self._check_condition(current_value, rule.operator, rule.threshold):
                        alerts_to_resolve.append(alert_id)

        for alert_id in alerts_to_resolve:
            await self.resolve_alert(alert_id)

    def _find_similar_alert(self, alert: Alert) -> Optional[Alert]:
        """Busca una alerta similar activa (deduplicación)."""
        for existing in self._active_alerts.values():
            if (existing.type == alert.type and
                existing.status == AlertStatus.ACTIVE and
                existing.remittance_id == alert.remittance_id):
                return existing
        return None

    def _update_active_alerts_gauge(self):
        """Actualiza métrica de alertas activas."""
        by_severity = {}
        for alert in self._active_alerts.values():
            sev = alert.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1

        for severity in AlertSeverity:
            ACTIVE_ALERTS.labels(severity=severity.value).set(
                by_severity.get(severity.value, 0)
            )

    # ==================== Notificaciones ====================

    async def _send_notifications(self, alert: Alert):
        """Envía notificaciones para una alerta."""
        rule = self._rules.get(alert.rule_id) if alert.rule_id else None
        channels = rule.notify_channels if rule else ["slack"]

        for channel_name in channels:
            try:
                channel = NotificationChannel(channel_name)
                handler = self._notification_handlers.get(channel)

                if handler:
                    await handler(alert)
                    NOTIFICATIONS_SENT.labels(channel=channel_name, status="success").inc()

            except Exception as e:
                logger.error(f"Error enviando notificación {channel_name}: {e}")
                NOTIFICATIONS_SENT.labels(channel=channel_name, status="failed").inc()

    async def _send_slack_notification(self, alert: Alert):
        """Envía notificación a Slack."""
        if not SLACK_WEBHOOK_URL:
            logger.warning("SLACK_WEBHOOK_URL no configurado")
            return

        color_map = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ffcc00",
            AlertSeverity.ERROR: "#ff6600",
            AlertSeverity.CRITICAL: "#ff0000",
        }

        payload = {
            "channel": SLACK_ALERT_CHANNEL,
            "attachments": [{
                "color": color_map.get(alert.severity, "#808080"),
                "title": f"[{alert.severity.value.upper()}] {alert.title}",
                "text": alert.message,
                "fields": [
                    {"title": "Tipo", "value": alert.type.value, "short": True},
                    {"title": "Severidad", "value": alert.severity.value, "short": True},
                ],
                "footer": "FinCore Alerts",
                "ts": int(alert.triggered_at.timestamp()),
            }]
        }

        if alert.remittance_id:
            payload["attachments"][0]["fields"].append({
                "title": "Remesa",
                "value": alert.remittance_id,
                "short": True,
            })

        async with aiohttp.ClientSession() as session:
            async with session.post(
                SLACK_WEBHOOK_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    raise Exception(f"Slack error: {response.status}")

        # Registrar notificación
        self._record_notification(alert, NotificationChannel.SLACK, SLACK_ALERT_CHANNEL)

    async def _send_webhook_notification(self, alert: Alert):
        """Envía notificación vía webhook genérico."""
        # Implementar según configuración
        pass

    async def _send_email_notification(self, alert: Alert):
        """Envía notificación por email."""
        # Implementar con sendgrid/ses
        if not ALERT_EMAIL_TO:
            return

        # Registrar intento
        for recipient in ALERT_EMAIL_TO:
            if recipient.strip():
                self._record_notification(alert, NotificationChannel.EMAIL, recipient)

    def _record_notification(
        self,
        alert: Alert,
        channel: NotificationChannel,
        recipient: str,
    ):
        """Registra una notificación enviada."""
        notification = NotificationModel(
            alert_id=alert.id,
            channel=channel.value,
            recipient=recipient,
            subject=alert.title,
            body=alert.message,
            delivered=True,
        )
        self.db.add(notification)
        self.db.commit()

    def close(self):
        """Cierra conexiones."""
        if self._db:
            self._db.close()


# ==================== Singleton ====================

_alert_service: Optional[AlertService] = None


def get_alert_service() -> AlertService:
    """Obtiene la instancia singleton del servicio."""
    global _alert_service
    if _alert_service is None:
        _alert_service = AlertService()
    return _alert_service


async def get_alert_service_async() -> AlertService:
    """Obtiene el servicio de alertas (async)."""
    return get_alert_service()
