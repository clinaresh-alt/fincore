"""
Servicio de Seguridad para FinCore.

Implementa controles de seguridad de grado institucional:
- Kill Switch para emergencias (pausa inmediata)
- Rotación automática de secretos (HashiCorp Vault)
- Detección de intrusiones y alertas
- Monitoreo de actividad sospechosa
- Gestión de accesos privilegiados

Uso:
    from app.services.security_service import SecurityService, security_service

    # Kill Switch
    await security_service.activate_kill_switch(
        reason="Actividad sospechosa detectada",
        initiated_by="admin@fincore.com",
    )

    # Verificar estado
    if security_service.is_system_paused():
        raise SystemPausedError("Sistema en modo emergencia")
"""
import os
import json
import logging
import asyncio
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

import aiohttp
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base, SessionLocal

# Prometheus metrics
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)


# ==================== Configuración ====================

# HashiCorp Vault
VAULT_ADDR = os.getenv("VAULT_ADDR", "http://localhost:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN", "")
VAULT_SECRET_PATH = os.getenv("VAULT_SECRET_PATH", "secret/data/fincore")

# AWS GuardDuty (opcional)
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
GUARDDUTY_DETECTOR_ID = os.getenv("GUARDDUTY_DETECTOR_ID", "")

# Alertas
ALERT_WEBHOOK_URL = os.getenv("SECURITY_ALERT_WEBHOOK", "")
PAGERDUTY_SERVICE_KEY = os.getenv("PAGERDUTY_SERVICE_KEY", "")
SLACK_SECURITY_WEBHOOK = os.getenv("SLACK_SECURITY_WEBHOOK", "")

# Umbrales de detección
MAX_FAILED_LOGINS = int(os.getenv("MAX_FAILED_LOGINS", "5"))
MAX_REQUESTS_PER_MINUTE = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "100"))
SUSPICIOUS_AMOUNT_THRESHOLD = int(os.getenv("SUSPICIOUS_AMOUNT_USD", "100000"))

# Rotación de secretos (horas)
SECRET_ROTATION_INTERVAL = int(os.getenv("SECRET_ROTATION_HOURS", "24"))


# ==================== Métricas Prometheus ====================

KILL_SWITCH_ACTIVATIONS = Counter(
    'security_kill_switch_activations_total',
    'Activaciones del kill switch',
    ['reason_category']
)

SECURITY_ALERTS = Counter(
    'security_alerts_total',
    'Alertas de seguridad generadas',
    ['severity', 'type']
)

FAILED_AUTH_ATTEMPTS = Counter(
    'security_failed_auth_total',
    'Intentos de autenticación fallidos',
    ['source']
)

SECRET_ROTATIONS = Counter(
    'security_secret_rotations_total',
    'Rotaciones de secretos realizadas',
    ['secret_type']
)

SYSTEM_STATUS = Gauge(
    'security_system_status',
    'Estado del sistema (1=running, 0=paused)'
)

INTRUSION_SCORE = Gauge(
    'security_intrusion_score',
    'Puntuación de riesgo de intrusión (0-100)'
)


# ==================== Tipos ====================

class AlertSeverity(str, Enum):
    """Niveles de severidad de alertas."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Tipos de alertas de seguridad."""
    FAILED_AUTH = "failed_auth"
    BRUTE_FORCE = "brute_force"
    UNUSUAL_ACTIVITY = "unusual_activity"
    LARGE_TRANSACTION = "large_transaction"
    CONFIG_CHANGE = "config_change"
    KILL_SWITCH = "kill_switch"
    INTRUSION_DETECTED = "intrusion_detected"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    IP_BLOCKED = "ip_blocked"
    SECRET_ACCESS = "secret_access"


class KillSwitchReason(str, Enum):
    """Razones para activar el kill switch."""
    INTRUSION_DETECTED = "intrusion_detected"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    MANUAL_ACTIVATION = "manual_activation"
    SMART_CONTRACT_EXPLOIT = "smart_contract_exploit"
    ORACLE_MANIPULATION = "oracle_manipulation"
    LIQUIDITY_DRAIN = "liquidity_drain"
    SCHEDULED_MAINTENANCE = "scheduled_maintenance"
    REGULATORY_COMPLIANCE = "regulatory_compliance"


@dataclass
class SecurityAlert:
    """Alerta de seguridad."""
    id: str
    severity: AlertSeverity
    alert_type: AlertType
    title: str
    description: str
    source_ip: Optional[str]
    user_id: Optional[str]
    metadata: Dict
    created_at: datetime
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    resolved: bool = False


@dataclass
class KillSwitchStatus:
    """Estado del kill switch."""
    is_active: bool
    activated_at: Optional[datetime]
    activated_by: Optional[str]
    reason: Optional[str]
    affected_services: List[str]
    estimated_resolution: Optional[datetime]


@dataclass
class SecretRotationResult:
    """Resultado de rotación de secreto."""
    secret_name: str
    rotated_at: datetime
    next_rotation: datetime
    version: int
    success: bool
    error: Optional[str] = None


# ==================== Modelos de DB ====================

class SecurityAlertModel(Base):
    """Alertas de seguridad en DB."""
    __tablename__ = "security_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    severity = Column(String(20), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    # Fuente
    source_ip = Column(String(45), nullable=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    extra_data = Column(JSONB, default={})

    # Estado
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(255), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class KillSwitchLogModel(Base):
    """Log de activaciones del kill switch."""
    __tablename__ = "kill_switch_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    action = Column(String(20), nullable=False)  # activate, deactivate
    reason = Column(String(100), nullable=False)
    reason_details = Column(Text, nullable=True)
    initiated_by = Column(String(255), nullable=False)
    affected_services = Column(JSONB, default=[])

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class SecretRotationLogModel(Base):
    """Log de rotaciones de secretos."""
    __tablename__ = "secret_rotation_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    secret_name = Column(String(100), nullable=False, index=True)
    secret_type = Column(String(50), nullable=False)
    version = Column(Integer, nullable=False)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    rotated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    next_rotation = Column(DateTime(timezone=True), nullable=True)


class IPBlocklistModel(Base):
    """IPs bloqueadas."""
    __tablename__ = "ip_blocklist"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    ip_address = Column(String(45), nullable=False, unique=True, index=True)
    reason = Column(String(255), nullable=False)
    blocked_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    blocked_until = Column(DateTime(timezone=True), nullable=True)
    permanent = Column(Boolean, default=False)
    blocked_by = Column(String(255), nullable=True)


# ==================== Servicio Principal ====================

class SecurityService:
    """
    Servicio de seguridad empresarial.

    Features:
    - Kill Switch para pausar operaciones críticas
    - Rotación automática de secretos via Vault
    - Detección de intrusiones
    - Monitoreo de actividad sospechosa
    - Alertas multi-canal (Slack, PagerDuty, webhooks)
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._kill_switch_active = False
        self._kill_switch_info: Optional[KillSwitchStatus] = None
        self._blocked_ips: set = set()
        self._failed_auth_tracker: Dict[str, List[datetime]] = {}
        self._rate_limit_tracker: Dict[str, List[datetime]] = {}
        self._alert_callbacks: List[Callable] = []

        # Cargar estado inicial
        self._load_initial_state()

        # Métrica inicial
        SYSTEM_STATUS.set(1)

    def _load_initial_state(self):
        """Carga estado inicial desde DB."""
        try:
            # Cargar IPs bloqueadas
            blocked = self.db.query(IPBlocklistModel).filter(
                IPBlocklistModel.blocked_until > datetime.utcnow()
            ).all()
            self._blocked_ips = {b.ip_address for b in blocked}

            # Verificar si hay kill switch activo
            last_log = self.db.query(KillSwitchLogModel).order_by(
                KillSwitchLogModel.created_at.desc()
            ).first()

            if last_log and last_log.action == "activate" and not last_log.resolved_at:
                self._kill_switch_active = True
                self._kill_switch_info = KillSwitchStatus(
                    is_active=True,
                    activated_at=last_log.created_at,
                    activated_by=last_log.initiated_by,
                    reason=last_log.reason,
                    affected_services=last_log.affected_services or [],
                    estimated_resolution=None,
                )
                SYSTEM_STATUS.set(0)

            logger.info(
                f"SecurityService inicializado: "
                f"kill_switch={self._kill_switch_active}, "
                f"blocked_ips={len(self._blocked_ips)}"
            )

        except Exception as e:
            logger.error(f"Error cargando estado de seguridad: {e}")

    @property
    def db(self) -> Session:
        """Obtiene sesión de DB."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    # ==================== Kill Switch ====================

    async def activate_kill_switch(
        self,
        reason: str,
        initiated_by: str,
        reason_details: Optional[str] = None,
        affected_services: Optional[List[str]] = None,
        estimated_resolution: Optional[datetime] = None,
    ) -> KillSwitchStatus:
        """
        Activa el kill switch de emergencia.

        Esto pausa todas las operaciones críticas:
        - Nuevas remesas
        - Liberaciones de escrow
        - Reembolsos
        - Transacciones blockchain

        Args:
            reason: Razón de la activación
            initiated_by: Usuario/sistema que inicia
            reason_details: Detalles adicionales
            affected_services: Servicios específicos a pausar
            estimated_resolution: Tiempo estimado de resolución

        Returns:
            Estado del kill switch
        """
        if self._kill_switch_active:
            logger.warning("Kill switch ya está activo")
            return self._kill_switch_info

        self._kill_switch_active = True
        now = datetime.utcnow()

        services = affected_services or [
            "remittance_service",
            "relayer_service",
            "blockchain_service",
            "bank_integration_service",
        ]

        self._kill_switch_info = KillSwitchStatus(
            is_active=True,
            activated_at=now,
            activated_by=initiated_by,
            reason=reason,
            affected_services=services,
            estimated_resolution=estimated_resolution,
        )

        # Registrar en DB
        log = KillSwitchLogModel(
            action="activate",
            reason=reason,
            reason_details=reason_details,
            initiated_by=initiated_by,
            affected_services=services,
        )
        self.db.add(log)
        self.db.commit()

        # Métricas
        reason_category = self._categorize_reason(reason)
        KILL_SWITCH_ACTIVATIONS.labels(reason_category=reason_category).inc()
        SYSTEM_STATUS.set(0)

        # Pausar contratos on-chain si es necesario
        await self._pause_smart_contracts()

        # Enviar alertas
        await self.create_alert(
            severity=AlertSeverity.CRITICAL,
            alert_type=AlertType.KILL_SWITCH,
            title="KILL SWITCH ACTIVADO",
            description=f"Sistema pausado por: {reason}. Iniciado por: {initiated_by}",
            metadata={
                "reason": reason,
                "initiated_by": initiated_by,
                "affected_services": services,
            },
        )

        logger.critical(f"KILL SWITCH ACTIVADO: {reason} (por {initiated_by})")

        return self._kill_switch_info

    async def deactivate_kill_switch(
        self,
        initiated_by: str,
        resolution_notes: Optional[str] = None,
    ) -> KillSwitchStatus:
        """
        Desactiva el kill switch.

        Args:
            initiated_by: Usuario que desactiva
            resolution_notes: Notas de resolución

        Returns:
            Estado actualizado
        """
        if not self._kill_switch_active:
            logger.warning("Kill switch no está activo")
            return KillSwitchStatus(
                is_active=False,
                activated_at=None,
                activated_by=None,
                reason=None,
                affected_services=[],
                estimated_resolution=None,
            )

        # Actualizar log anterior
        last_log = self.db.query(KillSwitchLogModel).filter(
            KillSwitchLogModel.action == "activate",
            KillSwitchLogModel.resolved_at == None,
        ).order_by(KillSwitchLogModel.created_at.desc()).first()

        if last_log:
            last_log.resolved_at = datetime.utcnow()

        # Nuevo log de desactivación
        log = KillSwitchLogModel(
            action="deactivate",
            reason="resolution",
            reason_details=resolution_notes,
            initiated_by=initiated_by,
            affected_services=self._kill_switch_info.affected_services if self._kill_switch_info else [],
        )
        self.db.add(log)
        self.db.commit()

        # Despausar contratos
        await self._unpause_smart_contracts()

        self._kill_switch_active = False
        self._kill_switch_info = None
        SYSTEM_STATUS.set(1)

        # Alerta de resolución
        await self.create_alert(
            severity=AlertSeverity.INFO,
            alert_type=AlertType.KILL_SWITCH,
            title="Kill Switch Desactivado",
            description=f"Sistema restaurado por: {initiated_by}",
            metadata={"resolution_notes": resolution_notes},
        )

        logger.info(f"Kill switch desactivado por {initiated_by}")

        return KillSwitchStatus(
            is_active=False,
            activated_at=None,
            activated_by=None,
            reason=None,
            affected_services=[],
            estimated_resolution=None,
        )

    def is_system_paused(self) -> bool:
        """Verifica si el sistema está pausado."""
        return self._kill_switch_active

    def get_kill_switch_status(self) -> KillSwitchStatus:
        """Obtiene estado actual del kill switch."""
        if self._kill_switch_info:
            return self._kill_switch_info
        return KillSwitchStatus(
            is_active=False,
            activated_at=None,
            activated_by=None,
            reason=None,
            affected_services=[],
            estimated_resolution=None,
        )

    async def _pause_smart_contracts(self):
        """Pausa los smart contracts vía multisig."""
        # Esto debería crear una propuesta multisig para pausar
        # Por ahora solo log
        logger.info("Iniciando pausa de smart contracts...")

    async def _unpause_smart_contracts(self):
        """Despausa los smart contracts vía multisig."""
        logger.info("Iniciando despausa de smart contracts...")

    def _categorize_reason(self, reason: str) -> str:
        """Categoriza la razón del kill switch."""
        reason_lower = reason.lower()
        if "intrusion" in reason_lower or "hack" in reason_lower:
            return "security_breach"
        elif "maintenance" in reason_lower:
            return "maintenance"
        elif "exploit" in reason_lower or "vulnerability" in reason_lower:
            return "vulnerability"
        elif "regulatory" in reason_lower or "compliance" in reason_lower:
            return "compliance"
        else:
            return "other"

    # ==================== Alertas ====================

    async def create_alert(
        self,
        severity: AlertSeverity,
        alert_type: AlertType,
        title: str,
        description: str,
        source_ip: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> SecurityAlert:
        """
        Crea una alerta de seguridad.

        Args:
            severity: Nivel de severidad
            alert_type: Tipo de alerta
            title: Título breve
            description: Descripción detallada
            source_ip: IP de origen
            user_id: ID de usuario involucrado
            metadata: Datos adicionales

        Returns:
            Alerta creada
        """
        alert_id = str(uuid4())

        alert = SecurityAlert(
            id=alert_id,
            severity=severity,
            alert_type=alert_type,
            title=title,
            description=description,
            source_ip=source_ip,
            user_id=user_id,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
        )

        # Guardar en DB
        db_alert = SecurityAlertModel(
            id=alert_id,
            severity=severity.value,
            alert_type=alert_type.value,
            title=title,
            description=description,
            source_ip=source_ip,
            user_id=user_id,
            extra_data=metadata or {},
        )
        self.db.add(db_alert)
        self.db.commit()

        # Métricas
        SECURITY_ALERTS.labels(
            severity=severity.value,
            type=alert_type.value
        ).inc()

        # Enviar notificaciones según severidad
        await self._send_alert_notifications(alert)

        # Callbacks locales
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Error en callback de alerta: {e}")

        logger.warning(f"Alerta de seguridad: [{severity.value}] {title}")

        return alert

    async def _send_alert_notifications(self, alert: SecurityAlert):
        """Envía notificaciones según severidad."""
        # Slack para todas las alertas
        if SLACK_SECURITY_WEBHOOK and alert.severity in (
            AlertSeverity.HIGH, AlertSeverity.CRITICAL
        ):
            await self._send_slack_alert(alert)

        # PagerDuty para críticas
        if PAGERDUTY_SERVICE_KEY and alert.severity == AlertSeverity.CRITICAL:
            await self._send_pagerduty_alert(alert)

        # Webhook genérico
        if ALERT_WEBHOOK_URL:
            await self._send_webhook_alert(alert)

    async def _send_slack_alert(self, alert: SecurityAlert):
        """Envía alerta a Slack."""
        color = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.LOW: "#ffcc00",
            AlertSeverity.MEDIUM: "#ff9900",
            AlertSeverity.HIGH: "#ff6600",
            AlertSeverity.CRITICAL: "#ff0000",
        }.get(alert.severity, "#cccccc")

        payload = {
            "attachments": [{
                "color": color,
                "title": f"[{alert.severity.value.upper()}] {alert.title}",
                "text": alert.description,
                "fields": [
                    {"title": "Tipo", "value": alert.alert_type.value, "short": True},
                    {"title": "IP", "value": alert.source_ip or "N/A", "short": True},
                ],
                "ts": int(alert.created_at.timestamp()),
            }]
        }

        try:
            async with aiohttp.ClientSession() as session:
                await session.post(SLACK_SECURITY_WEBHOOK, json=payload)
        except Exception as e:
            logger.error(f"Error enviando a Slack: {e}")

    async def _send_pagerduty_alert(self, alert: SecurityAlert):
        """Envía alerta a PagerDuty."""
        payload = {
            "routing_key": PAGERDUTY_SERVICE_KEY,
            "event_action": "trigger",
            "payload": {
                "summary": f"{alert.title}: {alert.description}",
                "severity": "critical",
                "source": "fincore-security",
                "custom_details": alert.metadata,
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=payload
                )
        except Exception as e:
            logger.error(f"Error enviando a PagerDuty: {e}")

    async def _send_webhook_alert(self, alert: SecurityAlert):
        """Envía alerta via webhook."""
        payload = {
            "id": alert.id,
            "severity": alert.severity.value,
            "type": alert.alert_type.value,
            "title": alert.title,
            "description": alert.description,
            "source_ip": alert.source_ip,
            "timestamp": alert.created_at.isoformat(),
            "metadata": alert.metadata,
        }

        try:
            async with aiohttp.ClientSession() as session:
                await session.post(ALERT_WEBHOOK_URL, json=payload)
        except Exception as e:
            logger.error(f"Error enviando webhook: {e}")

    def register_alert_callback(self, callback: Callable):
        """Registra un callback para alertas."""
        self._alert_callbacks.append(callback)

    # ==================== Rotación de Secretos ====================

    async def rotate_secret(
        self,
        secret_name: str,
        secret_type: str = "api_key",
    ) -> SecretRotationResult:
        """
        Rota un secreto en HashiCorp Vault.

        Args:
            secret_name: Nombre del secreto
            secret_type: Tipo (api_key, db_password, etc.)

        Returns:
            Resultado de la rotación
        """
        if not VAULT_TOKEN:
            return SecretRotationResult(
                secret_name=secret_name,
                rotated_at=datetime.utcnow(),
                next_rotation=datetime.utcnow() + timedelta(hours=SECRET_ROTATION_INTERVAL),
                version=0,
                success=False,
                error="Vault no configurado",
            )

        try:
            # Generar nuevo valor
            new_value = self._generate_secret_value(secret_type)

            # Obtener versión actual
            current_version = await self._get_vault_secret_version(secret_name)

            # Guardar en Vault
            success = await self._update_vault_secret(secret_name, new_value)

            if success:
                new_version = current_version + 1
                next_rotation = datetime.utcnow() + timedelta(hours=SECRET_ROTATION_INTERVAL)

                # Registrar en DB
                log = SecretRotationLogModel(
                    secret_name=secret_name,
                    secret_type=secret_type,
                    version=new_version,
                    success=True,
                    next_rotation=next_rotation,
                )
                self.db.add(log)
                self.db.commit()

                SECRET_ROTATIONS.labels(secret_type=secret_type).inc()

                logger.info(f"Secreto rotado: {secret_name} (v{new_version})")

                return SecretRotationResult(
                    secret_name=secret_name,
                    rotated_at=datetime.utcnow(),
                    next_rotation=next_rotation,
                    version=new_version,
                    success=True,
                )

            raise Exception("Fallo al actualizar en Vault")

        except Exception as e:
            logger.error(f"Error rotando secreto {secret_name}: {e}")

            log = SecretRotationLogModel(
                secret_name=secret_name,
                secret_type=secret_type,
                version=0,
                success=False,
                error_message=str(e),
            )
            self.db.add(log)
            self.db.commit()

            return SecretRotationResult(
                secret_name=secret_name,
                rotated_at=datetime.utcnow(),
                next_rotation=datetime.utcnow(),
                version=0,
                success=False,
                error=str(e),
            )

    def _generate_secret_value(self, secret_type: str) -> str:
        """Genera un nuevo valor de secreto."""
        if secret_type == "api_key":
            return f"fk_{secrets.token_urlsafe(32)}"
        elif secret_type == "db_password":
            return secrets.token_urlsafe(24)
        elif secret_type == "jwt_secret":
            return secrets.token_hex(32)
        else:
            return secrets.token_urlsafe(32)

    async def _get_vault_secret_version(self, secret_name: str) -> int:
        """Obtiene la versión actual de un secreto en Vault."""
        url = f"{VAULT_ADDR}/v1/{VAULT_SECRET_PATH}/{secret_name}"
        headers = {"X-Vault-Token": VAULT_TOKEN}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("data", {}).get("metadata", {}).get("version", 0)
                    return 0
        except:
            return 0

    async def _update_vault_secret(self, secret_name: str, value: str) -> bool:
        """Actualiza un secreto en Vault."""
        url = f"{VAULT_ADDR}/v1/{VAULT_SECRET_PATH}/{secret_name}"
        headers = {"X-Vault-Token": VAULT_TOKEN}
        payload = {"data": {"value": value}}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    return response.status in (200, 204)
        except Exception as e:
            logger.error(f"Error actualizando Vault: {e}")
            return False

    async def rotate_all_secrets(self) -> List[SecretRotationResult]:
        """Rota todos los secretos que necesitan rotación."""
        secrets_to_rotate = [
            ("api_key_primary", "api_key"),
            ("api_key_secondary", "api_key"),
            ("webhook_secret", "api_key"),
            ("jwt_secret", "jwt_secret"),
        ]

        results = []
        for secret_name, secret_type in secrets_to_rotate:
            result = await self.rotate_secret(secret_name, secret_type)
            results.append(result)

        return results

    # ==================== Detección de Intrusiones ====================

    async def record_failed_auth(
        self,
        source_ip: str,
        user_identifier: Optional[str] = None,
    ):
        """
        Registra un intento de autenticación fallido.

        Args:
            source_ip: IP del intento
            user_identifier: Email o ID del usuario
        """
        now = datetime.utcnow()

        # Tracking por IP
        if source_ip not in self._failed_auth_tracker:
            self._failed_auth_tracker[source_ip] = []

        # Limpiar intentos viejos (últimos 15 minutos)
        cutoff = now - timedelta(minutes=15)
        self._failed_auth_tracker[source_ip] = [
            t for t in self._failed_auth_tracker[source_ip] if t > cutoff
        ]

        self._failed_auth_tracker[source_ip].append(now)
        FAILED_AUTH_ATTEMPTS.labels(source=source_ip[:20]).inc()

        # Verificar si excede umbral
        if len(self._failed_auth_tracker[source_ip]) >= MAX_FAILED_LOGINS:
            await self._handle_brute_force(source_ip, user_identifier)

    async def _handle_brute_force(self, ip: str, user_identifier: Optional[str]):
        """Maneja detección de fuerza bruta."""
        # Bloquear IP
        await self.block_ip(ip, "Brute force detected", hours=1)

        # Crear alerta
        await self.create_alert(
            severity=AlertSeverity.HIGH,
            alert_type=AlertType.BRUTE_FORCE,
            title="Ataque de Fuerza Bruta Detectado",
            description=f"Múltiples intentos fallidos desde {ip}",
            source_ip=ip,
            metadata={"user_identifier": user_identifier},
        )

        # Incrementar score de intrusión
        current_score = INTRUSION_SCORE._value._value if hasattr(INTRUSION_SCORE, '_value') else 0
        INTRUSION_SCORE.set(min(current_score + 10, 100))

    async def block_ip(
        self,
        ip_address: str,
        reason: str,
        hours: int = 24,
        permanent: bool = False,
        blocked_by: Optional[str] = None,
    ):
        """Bloquea una IP."""
        blocked_until = None if permanent else datetime.utcnow() + timedelta(hours=hours)

        block = IPBlocklistModel(
            ip_address=ip_address,
            reason=reason,
            blocked_until=blocked_until,
            permanent=permanent,
            blocked_by=blocked_by,
        )
        self.db.add(block)
        self.db.commit()

        self._blocked_ips.add(ip_address)

        await self.create_alert(
            severity=AlertSeverity.MEDIUM,
            alert_type=AlertType.IP_BLOCKED,
            title="IP Bloqueada",
            description=f"IP {ip_address} bloqueada: {reason}",
            source_ip=ip_address,
        )

        logger.warning(f"IP bloqueada: {ip_address} - {reason}")

    def is_ip_blocked(self, ip_address: str) -> bool:
        """Verifica si una IP está bloqueada."""
        return ip_address in self._blocked_ips

    async def check_rate_limit(
        self,
        identifier: str,
        max_requests: int = MAX_REQUESTS_PER_MINUTE,
    ) -> bool:
        """
        Verifica rate limit.

        Args:
            identifier: IP o user ID
            max_requests: Máximo de requests por minuto

        Returns:
            True si está dentro del límite
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)

        if identifier not in self._rate_limit_tracker:
            self._rate_limit_tracker[identifier] = []

        # Limpiar viejos
        self._rate_limit_tracker[identifier] = [
            t for t in self._rate_limit_tracker[identifier] if t > cutoff
        ]

        if len(self._rate_limit_tracker[identifier]) >= max_requests:
            await self.create_alert(
                severity=AlertSeverity.MEDIUM,
                alert_type=AlertType.RATE_LIMIT_EXCEEDED,
                title="Rate Limit Excedido",
                description=f"Demasiadas requests desde {identifier}",
                source_ip=identifier if "." in identifier else None,
            )
            return False

        self._rate_limit_tracker[identifier].append(now)
        return True

    # ==================== Consultas ====================

    def get_recent_alerts(
        self,
        limit: int = 50,
        severity: Optional[AlertSeverity] = None,
    ) -> List[SecurityAlert]:
        """Obtiene alertas recientes."""
        query = self.db.query(SecurityAlertModel).order_by(
            SecurityAlertModel.created_at.desc()
        )

        if severity:
            query = query.filter(SecurityAlertModel.severity == severity.value)

        alerts = query.limit(limit).all()

        return [
            SecurityAlert(
                id=str(a.id),
                severity=AlertSeverity(a.severity),
                alert_type=AlertType(a.alert_type),
                title=a.title,
                description=a.description,
                source_ip=a.source_ip,
                user_id=str(a.user_id) if a.user_id else None,
                metadata=a.extra_data or {},
                created_at=a.created_at,
                acknowledged=a.acknowledged,
                acknowledged_by=a.acknowledged_by,
                resolved=a.resolved,
            )
            for a in alerts
        ]

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Marca una alerta como reconocida."""
        alert = self.db.query(SecurityAlertModel).filter(
            SecurityAlertModel.id == alert_id
        ).first()

        if alert:
            alert.acknowledged = True
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = datetime.utcnow()
            self.db.commit()
            return True

        return False

    def close(self):
        """Cierra conexiones."""
        if self._db:
            self._db.close()


# ==================== Singleton ====================

_security_service: Optional[SecurityService] = None


def get_security_service() -> SecurityService:
    """Obtiene la instancia singleton del servicio."""
    global _security_service
    if _security_service is None:
        _security_service = SecurityService()
    return _security_service


# Alias
security_service = get_security_service
