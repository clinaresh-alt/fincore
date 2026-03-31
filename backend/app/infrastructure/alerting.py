"""
Sistema de Alertas con integración PagerDuty, Slack, y Email.
Gestión de incidentes y escalamiento automático.
"""
import asyncio
import logging
import os
import json
import hashlib
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
import threading
import httpx

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Niveles de severidad de alertas."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @property
    def pagerduty_severity(self) -> str:
        """Mapea a severidad de PagerDuty."""
        mapping = {
            "info": "info",
            "warning": "warning",
            "error": "error",
            "critical": "critical",
        }
        return mapping.get(self.value, "error")


class AlertChannel(Enum):
    """Canales de notificación."""
    PAGERDUTY = "pagerduty"
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"


@dataclass
class Alert:
    """Representa una alerta."""
    title: str
    description: str
    severity: AlertSeverity
    source: str
    dedup_key: Optional[str] = None
    component: Optional[str] = None
    group: Optional[str] = None
    class_type: Optional[str] = None
    custom_details: Dict[str, Any] = field(default_factory=dict)
    links: List[Dict[str, str]] = field(default_factory=list)
    images: List[Dict[str, str]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        # Generar dedup_key si no se proporciona
        if not self.dedup_key:
            key_source = f"{self.source}:{self.component}:{self.title}"
            self.dedup_key = hashlib.md5(key_source.encode()).hexdigest()


@dataclass
class AlertRule:
    """Regla para filtrar y enrutar alertas."""
    name: str
    condition: Callable[[Alert], bool]
    channels: List[AlertChannel]
    throttle_seconds: int = 300  # Tiempo mínimo entre alertas duplicadas
    escalate_after_minutes: Optional[int] = None


class AlertingService:
    """
    Servicio central de alertas.
    Soporta PagerDuty, Slack, Email y webhooks personalizados.
    """

    def __init__(
        self,
        pagerduty_routing_key: Optional[str] = None,
        slack_webhook_url: Optional[str] = None,
        custom_webhook_url: Optional[str] = None,
        email_config: Optional[Dict[str, str]] = None,
        default_channels: Optional[List[AlertChannel]] = None,
    ):
        """
        Inicializa el servicio de alertas.

        Args:
            pagerduty_routing_key: Routing key de PagerDuty Events API v2
            slack_webhook_url: URL del webhook de Slack
            custom_webhook_url: URL de webhook personalizado
            email_config: Configuración de email
            default_channels: Canales por defecto
        """
        self.pagerduty_routing_key = pagerduty_routing_key or os.getenv(
            "PAGERDUTY_ROUTING_KEY"
        )
        self.slack_webhook_url = slack_webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.custom_webhook_url = custom_webhook_url or os.getenv("ALERT_WEBHOOK_URL")
        self.email_config = email_config

        self.default_channels = default_channels or [AlertChannel.PAGERDUTY]

        # Throttling: tracking de alertas recientes
        self._alert_history: Dict[str, datetime] = {}
        self._history_lock = threading.Lock()

        # Reglas de enrutamiento
        self._rules: List[AlertRule] = []

        # HTTP client para requests
        self._client: Optional[httpx.AsyncClient] = None

        logger.info(
            f"AlertingService initialized. "
            f"PagerDuty: {'configured' if self.pagerduty_routing_key else 'not configured'}, "
            f"Slack: {'configured' if self.slack_webhook_url else 'not configured'}"
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Obtiene o crea el cliente HTTP."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    def add_rule(self, rule: AlertRule) -> None:
        """Añade una regla de enrutamiento."""
        self._rules.append(rule)
        logger.debug(f"Added alert rule: {rule.name}")

    def _should_throttle(self, dedup_key: str, throttle_seconds: int) -> bool:
        """Verifica si la alerta debe ser throttled."""
        with self._history_lock:
            last_sent = self._alert_history.get(dedup_key)
            if last_sent:
                if datetime.utcnow() - last_sent < timedelta(seconds=throttle_seconds):
                    return True
            return False

    def _record_alert(self, dedup_key: str) -> None:
        """Registra que se envió una alerta."""
        with self._history_lock:
            self._alert_history[dedup_key] = datetime.utcnow()

            # Limpiar alertas antiguas (más de 1 hora)
            cutoff = datetime.utcnow() - timedelta(hours=1)
            self._alert_history = {
                k: v for k, v in self._alert_history.items() if v > cutoff
            }

    def _get_channels_for_alert(self, alert: Alert) -> List[AlertChannel]:
        """Determina los canales para una alerta basado en reglas."""
        for rule in self._rules:
            if rule.condition(alert):
                if self._should_throttle(alert.dedup_key, rule.throttle_seconds):
                    logger.debug(
                        f"Alert throttled by rule '{rule.name}': {alert.title}"
                    )
                    return []
                return rule.channels
        return self.default_channels

    async def send_alert(
        self,
        alert: Alert,
        channels: Optional[List[AlertChannel]] = None,
    ) -> Dict[str, bool]:
        """
        Envía una alerta a los canales especificados.

        Args:
            alert: La alerta a enviar
            channels: Canales específicos (opcional, usa reglas si no se especifica)

        Returns:
            Dict con el resultado de cada canal
        """
        if channels is None:
            channels = self._get_channels_for_alert(alert)

        if not channels:
            return {}

        results = {}

        for channel in channels:
            try:
                if channel == AlertChannel.PAGERDUTY:
                    results["pagerduty"] = await self._send_pagerduty(alert)
                elif channel == AlertChannel.SLACK:
                    results["slack"] = await self._send_slack(alert)
                elif channel == AlertChannel.WEBHOOK:
                    results["webhook"] = await self._send_webhook(alert)
                elif channel == AlertChannel.EMAIL:
                    results["email"] = await self._send_email(alert)
            except Exception as e:
                logger.error(f"Failed to send alert to {channel.value}: {e}")
                results[channel.value] = False

        # Registrar que se envió la alerta
        if any(results.values()):
            self._record_alert(alert.dedup_key)

        return results

    async def _send_pagerduty(self, alert: Alert) -> bool:
        """Envía alerta a PagerDuty Events API v2."""
        if not self.pagerduty_routing_key:
            logger.warning("PagerDuty routing key not configured")
            return False

        payload = {
            "routing_key": self.pagerduty_routing_key,
            "event_action": "trigger",
            "dedup_key": alert.dedup_key,
            "payload": {
                "summary": alert.title,
                "severity": alert.severity.pagerduty_severity,
                "source": alert.source,
                "timestamp": alert.timestamp.isoformat() + "Z",
                "component": alert.component,
                "group": alert.group,
                "class": alert.class_type,
                "custom_details": {
                    "description": alert.description,
                    **alert.custom_details,
                },
            },
            "links": alert.links,
            "images": alert.images,
        }

        # Limpiar campos None
        payload["payload"] = {
            k: v for k, v in payload["payload"].items() if v is not None
        }

        client = await self._get_client()
        response = await client.post(
            "https://events.pagerduty.com/v2/enqueue",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 202:
            logger.info(f"PagerDuty alert sent: {alert.title}")
            return True
        else:
            logger.error(
                f"PagerDuty error: {response.status_code} - {response.text}"
            )
            return False

    async def _send_slack(self, alert: Alert) -> bool:
        """Envía alerta a Slack webhook."""
        if not self.slack_webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False

        # Mapeo de severidad a emoji y color
        severity_config = {
            AlertSeverity.INFO: {"emoji": ":information_source:", "color": "#36a64f"},
            AlertSeverity.WARNING: {"emoji": ":warning:", "color": "#ffcc00"},
            AlertSeverity.ERROR: {"emoji": ":x:", "color": "#ff6600"},
            AlertSeverity.CRITICAL: {"emoji": ":rotating_light:", "color": "#ff0000"},
        }

        config = severity_config.get(alert.severity, severity_config[AlertSeverity.ERROR])

        payload = {
            "attachments": [
                {
                    "color": config["color"],
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": f"{config['emoji']} {alert.title}",
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": alert.description,
                            },
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"*Source:* {alert.source} | *Severity:* {alert.severity.value} | *Time:* {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                                },
                            ],
                        },
                    ],
                }
            ]
        }

        # Añadir detalles custom si existen
        if alert.custom_details:
            fields = []
            for key, value in list(alert.custom_details.items())[:10]:
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*{key}:* {value}",
                })
            if fields:
                payload["attachments"][0]["blocks"].append({
                    "type": "section",
                    "fields": fields[:8],  # Slack limit
                })

        client = await self._get_client()
        response = await client.post(
            self.slack_webhook_url,
            json=payload,
        )

        if response.status_code == 200:
            logger.info(f"Slack alert sent: {alert.title}")
            return True
        else:
            logger.error(f"Slack error: {response.status_code} - {response.text}")
            return False

    async def _send_webhook(self, alert: Alert) -> bool:
        """Envía alerta a webhook personalizado."""
        if not self.custom_webhook_url:
            logger.warning("Custom webhook URL not configured")
            return False

        payload = {
            "title": alert.title,
            "description": alert.description,
            "severity": alert.severity.value,
            "source": alert.source,
            "component": alert.component,
            "group": alert.group,
            "class_type": alert.class_type,
            "dedup_key": alert.dedup_key,
            "custom_details": alert.custom_details,
            "timestamp": alert.timestamp.isoformat(),
        }

        client = await self._get_client()
        response = await client.post(
            self.custom_webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code in (200, 201, 202, 204):
            logger.info(f"Webhook alert sent: {alert.title}")
            return True
        else:
            logger.error(f"Webhook error: {response.status_code} - {response.text}")
            return False

    async def _send_email(self, alert: Alert) -> bool:
        """Envía alerta por email (via SendGrid)."""
        # Implementación simplificada - en producción usar SendGrid
        logger.info(f"Email alert would be sent: {alert.title}")
        return True

    async def resolve_alert(self, dedup_key: str) -> bool:
        """Resuelve una alerta en PagerDuty."""
        if not self.pagerduty_routing_key:
            return False

        payload = {
            "routing_key": self.pagerduty_routing_key,
            "event_action": "resolve",
            "dedup_key": dedup_key,
        }

        client = await self._get_client()
        response = await client.post(
            "https://events.pagerduty.com/v2/enqueue",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 202:
            logger.info(f"PagerDuty alert resolved: {dedup_key}")
            return True
        return False

    async def close(self) -> None:
        """Cierra el cliente HTTP."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Funciones helper para alertas comunes
def create_circuit_breaker_alert(
    name: str,
    state: str,
    failure_count: int,
) -> Alert:
    """Crea una alerta de circuit breaker."""
    severity = AlertSeverity.CRITICAL if state == "open" else AlertSeverity.WARNING
    return Alert(
        title=f"Circuit Breaker '{name}' is {state.upper()}",
        description=f"The circuit breaker for {name} has transitioned to {state} state after {failure_count} consecutive failures.",
        severity=severity,
        source="fincore-circuit-breaker",
        component=name,
        group="infrastructure",
        class_type="circuit_breaker",
        custom_details={
            "circuit_name": name,
            "state": state,
            "failure_count": failure_count,
        },
    )


def create_payment_failure_alert(
    provider: str,
    transaction_id: str,
    error: str,
    amount: float,
    currency: str,
) -> Alert:
    """Crea una alerta de fallo de pago."""
    return Alert(
        title=f"Payment Failed: {provider}",
        description=f"Payment transaction {transaction_id} failed: {error}",
        severity=AlertSeverity.ERROR,
        source="fincore-payments",
        component=provider,
        group="payments",
        class_type="payment_failure",
        custom_details={
            "provider": provider,
            "transaction_id": transaction_id,
            "error": error,
            "amount": amount,
            "currency": currency,
        },
    )


def create_security_alert(
    event_type: str,
    user_id: Optional[str],
    ip_address: str,
    details: str,
) -> Alert:
    """Crea una alerta de seguridad."""
    return Alert(
        title=f"Security Event: {event_type}",
        description=details,
        severity=AlertSeverity.CRITICAL,
        source="fincore-security",
        component="authentication",
        group="security",
        class_type=event_type,
        custom_details={
            "event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address,
        },
    )


# Instancia global del servicio
alert_service = AlertingService()
