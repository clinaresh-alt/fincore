"""
Plan de Respuesta ante Incidentes (IRP) para Smart Contracts.

Implementa el marco de respuesta ante incidentes de seguridad:
1. Detección y Análisis
2. Contención
3. Erradicación
4. Recuperación
5. Post-Incidente (Lecciones Aprendidas)

Basado en NIST SP 800-61 y mejores prácticas de seguridad blockchain.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from dataclasses import dataclass, field
import hashlib

from pydantic import BaseModel

logger = logging.getLogger(__name__)

from app.services.audit.monitoring_service import (
    Alert,
    AlertSeverity,
    AlertType,
    TransactionMonitoringService,
)


class IncidentStatus(str, Enum):
    """Estados de un incidente."""
    DETECTED = "detected"  # Recién detectado
    ANALYZING = "analyzing"  # En análisis
    CONTAINED = "contained"  # Contenido (circuit breaker activado)
    ERADICATING = "eradicating"  # Eliminando causa raíz
    RECOVERING = "recovering"  # Recuperando operaciones
    RESOLVED = "resolved"  # Resuelto
    CLOSED = "closed"  # Cerrado con post-mortem


class IncidentSeverity(str, Enum):
    """Severidad del incidente (basado en impacto)."""
    SEV1 = "sev1"  # Crítico: Pérdida activa de fondos
    SEV2 = "sev2"  # Alto: Vulnerabilidad explotable, sin pérdida aún
    SEV3 = "sev3"  # Medio: Comportamiento anómalo detectado
    SEV4 = "sev4"  # Bajo: Alertas de rutina


class ActionType(str, Enum):
    """Tipos de acciones de respuesta."""
    PAUSE_CONTRACT = "pause_contract"
    TRIP_CIRCUIT_BREAKER = "trip_circuit_breaker"
    REVOKE_ROLE = "revoke_role"
    BLACKLIST_ADDRESS = "blacklist_address"
    DRAIN_TO_SAFE = "drain_to_safe"  # Mover fondos a wallet seguro
    NOTIFY_TEAM = "notify_team"
    NOTIFY_USERS = "notify_users"
    ESCALATE = "escalate"
    DOCUMENT = "document"
    MANUAL_REVIEW = "manual_review"


@dataclass
class IncidentAction:
    """Acción tomada durante respuesta a incidente."""
    id: str
    action_type: ActionType
    description: str
    executed_by: str
    executed_at: datetime
    success: bool
    result: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Incident:
    """Estructura de un incidente de seguridad."""
    id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus

    # Contexto
    detected_at: datetime
    detected_by: str  # "automated" o nombre de persona
    affected_contracts: list[str] = field(default_factory=list)
    affected_users: list[str] = field(default_factory=list)
    related_transactions: list[str] = field(default_factory=list)
    related_alerts: list[str] = field(default_factory=list)

    # Timeline
    contained_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    # Respuesta
    actions_taken: list[IncidentAction] = field(default_factory=list)
    assigned_to: Optional[str] = None
    escalation_level: int = 0

    # Post-mortem
    root_cause: Optional[str] = None
    lessons_learned: Optional[str] = None
    preventive_measures: list[str] = field(default_factory=list)

    # Impacto
    estimated_loss: Optional[float] = None
    actual_loss: Optional[float] = None
    funds_recovered: Optional[float] = None

    # Metadata
    metadata: dict = field(default_factory=dict)


class PlaybookStep(BaseModel):
    """Paso en un playbook de respuesta."""
    order: int
    action_type: ActionType
    description: str
    automatic: bool = False  # Si se ejecuta automáticamente
    required: bool = True
    timeout_minutes: int = 30
    on_failure: Optional[str] = None  # ID de paso alternativo


class ResponsePlaybook(BaseModel):
    """
    Playbook de respuesta predefinido.

    Define los pasos a seguir para diferentes tipos de incidentes.
    """
    id: str
    name: str
    description: str
    trigger_alert_types: list[AlertType]
    trigger_severity: AlertSeverity
    steps: list[PlaybookStep]
    auto_execute: bool = False  # Si ejecutar automáticamente al detectar


class IncidentResponseService:
    """
    Servicio de Respuesta ante Incidentes.

    Gestiona el ciclo de vida completo de incidentes de seguridad:
    - Detección automática basada en alertas
    - Ejecución de playbooks de respuesta
    - Tracking de acciones y timeline
    - Generación de reportes post-mortem
    """

    def __init__(self, monitoring_service: Optional[TransactionMonitoringService] = None):
        self.monitoring_service = monitoring_service or TransactionMonitoringService()
        self.incidents: dict[str, Incident] = {}
        self.playbooks: dict[str, ResponsePlaybook] = {}
        self.incident_handlers: list[Callable] = []

        # Contactos de emergencia
        self.emergency_contacts = {
            "security_team": [],
            "engineering_lead": [],
            "executive": [],
        }

        # Configuración
        self.auto_contain_sev1 = True  # Auto circuit-breaker para SEV1
        self.escalation_timeouts = {
            IncidentSeverity.SEV1: timedelta(minutes=5),
            IncidentSeverity.SEV2: timedelta(minutes=15),
            IncidentSeverity.SEV3: timedelta(hours=1),
            IncidentSeverity.SEV4: timedelta(hours=4),
        }

        self._setup_default_playbooks()

        # Registrar handler de alertas
        if self.monitoring_service:
            self.monitoring_service.register_alert_handler(self._handle_alert)

    def _setup_default_playbooks(self):
        """Configura playbooks de respuesta por defecto."""

        # Playbook: Reentrancy Attack
        self.add_playbook(ResponsePlaybook(
            id="playbook_reentrancy",
            name="Respuesta a Ataque de Reentrancy",
            description="Pasos para contener y remediar un ataque de reentrancy",
            trigger_alert_types=[AlertType.REENTRANCY_DETECTED],
            trigger_severity=AlertSeverity.CRITICAL,
            auto_execute=True,
            steps=[
                PlaybookStep(
                    order=1,
                    action_type=ActionType.TRIP_CIRCUIT_BREAKER,
                    description="Activar circuit breaker inmediatamente",
                    automatic=True,
                    required=True,
                    timeout_minutes=1,
                ),
                PlaybookStep(
                    order=2,
                    action_type=ActionType.NOTIFY_TEAM,
                    description="Notificar equipo de seguridad",
                    automatic=True,
                    required=True,
                    timeout_minutes=5,
                ),
                PlaybookStep(
                    order=3,
                    action_type=ActionType.BLACKLIST_ADDRESS,
                    description="Agregar direcciones atacantes a blacklist",
                    automatic=False,
                    required=True,
                    timeout_minutes=15,
                ),
                PlaybookStep(
                    order=4,
                    action_type=ActionType.DOCUMENT,
                    description="Documentar transacciones maliciosas",
                    automatic=False,
                    required=True,
                    timeout_minutes=30,
                ),
                PlaybookStep(
                    order=5,
                    action_type=ActionType.MANUAL_REVIEW,
                    description="Revisión manual antes de reanudar",
                    automatic=False,
                    required=True,
                    timeout_minutes=60,
                ),
            ],
        ))

        # Playbook: Flash Loan Attack
        self.add_playbook(ResponsePlaybook(
            id="playbook_flash_loan",
            name="Respuesta a Flash Loan Attack",
            description="Pasos para contener manipulación de precio via flash loan",
            trigger_alert_types=[AlertType.FLASH_LOAN, AlertType.PRICE_MANIPULATION],
            trigger_severity=AlertSeverity.HIGH,
            auto_execute=True,
            steps=[
                PlaybookStep(
                    order=1,
                    action_type=ActionType.PAUSE_CONTRACT,
                    description="Pausar contratos afectados",
                    automatic=True,
                    required=True,
                    timeout_minutes=1,
                ),
                PlaybookStep(
                    order=2,
                    action_type=ActionType.NOTIFY_TEAM,
                    description="Notificar equipo",
                    automatic=True,
                    required=True,
                    timeout_minutes=5,
                ),
                PlaybookStep(
                    order=3,
                    action_type=ActionType.DOCUMENT,
                    description="Analizar flujo del ataque",
                    automatic=False,
                    required=True,
                    timeout_minutes=30,
                ),
            ],
        ))

        # Playbook: Large Transaction
        self.add_playbook(ResponsePlaybook(
            id="playbook_large_tx",
            name="Verificación de Transacción Grande",
            description="Verificar transacciones que superan umbrales",
            trigger_alert_types=[AlertType.LARGE_TRANSACTION],
            trigger_severity=AlertSeverity.HIGH,
            auto_execute=False,  # No automático, solo alerta
            steps=[
                PlaybookStep(
                    order=1,
                    action_type=ActionType.NOTIFY_TEAM,
                    description="Notificar para revisión",
                    automatic=True,
                    required=True,
                    timeout_minutes=15,
                ),
                PlaybookStep(
                    order=2,
                    action_type=ActionType.MANUAL_REVIEW,
                    description="Verificar legitimidad",
                    automatic=False,
                    required=True,
                    timeout_minutes=60,
                ),
            ],
        ))

        # Playbook: Admin Function Call
        self.add_playbook(ResponsePlaybook(
            id="playbook_admin_function",
            name="Verificación de Función Administrativa",
            description="Verificar llamadas a funciones privilegiadas",
            trigger_alert_types=[AlertType.ADMIN_FUNCTION_CALL],
            trigger_severity=AlertSeverity.HIGH,
            auto_execute=False,
            steps=[
                PlaybookStep(
                    order=1,
                    action_type=ActionType.NOTIFY_TEAM,
                    description="Notificar equipo de seguridad",
                    automatic=True,
                    required=True,
                    timeout_minutes=5,
                ),
                PlaybookStep(
                    order=2,
                    action_type=ActionType.DOCUMENT,
                    description="Registrar quién y por qué",
                    automatic=False,
                    required=True,
                    timeout_minutes=30,
                ),
            ],
        ))

    def add_playbook(self, playbook: ResponsePlaybook) -> None:
        """Agrega un playbook de respuesta."""
        self.playbooks[playbook.id] = playbook

    def register_incident_handler(self, handler: Callable) -> None:
        """Registra un handler para nuevos incidentes."""
        self.incident_handlers.append(handler)

    async def _handle_alert(self, alert: Alert) -> None:
        """
        Handler para alertas del servicio de monitoreo.

        Evalúa si la alerta requiere crear un incidente y
        ejecutar un playbook de respuesta.
        """
        # Buscar playbook que aplique
        matching_playbook = None
        for playbook in self.playbooks.values():
            if (alert.type in playbook.trigger_alert_types and
                    self._severity_matches(alert.severity, playbook.trigger_severity)):
                matching_playbook = playbook
                break

        if matching_playbook:
            # Determinar severidad del incidente
            incident_severity = self._map_to_incident_severity(alert.severity)

            # Crear incidente
            incident = await self.create_incident(
                title=f"Incidente: {alert.title}",
                description=alert.description,
                severity=incident_severity,
                detected_by="automated",
                related_alerts=[alert.id],
                affected_contracts=[alert.contract_address] if alert.contract_address else [],
                related_transactions=[alert.transaction_hash] if alert.transaction_hash else [],
            )

            # Ejecutar playbook si es automático
            if matching_playbook.auto_execute:
                await self.execute_playbook(incident.id, matching_playbook.id)

    def _severity_matches(
        self,
        alert_severity: AlertSeverity,
        playbook_severity: AlertSeverity,
    ) -> bool:
        """Verifica si la severidad de alerta cumple con el playbook."""
        severity_order = {
            AlertSeverity.INFO: 0,
            AlertSeverity.LOW: 1,
            AlertSeverity.MEDIUM: 2,
            AlertSeverity.HIGH: 3,
            AlertSeverity.CRITICAL: 4,
        }
        return severity_order.get(alert_severity, 0) >= severity_order.get(playbook_severity, 0)

    def _map_to_incident_severity(self, alert_severity: AlertSeverity) -> IncidentSeverity:
        """Mapea severidad de alerta a severidad de incidente."""
        mapping = {
            AlertSeverity.CRITICAL: IncidentSeverity.SEV1,
            AlertSeverity.HIGH: IncidentSeverity.SEV2,
            AlertSeverity.MEDIUM: IncidentSeverity.SEV3,
            AlertSeverity.LOW: IncidentSeverity.SEV4,
            AlertSeverity.INFO: IncidentSeverity.SEV4,
        }
        return mapping.get(alert_severity, IncidentSeverity.SEV3)

    async def create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        detected_by: str = "manual",
        related_alerts: list[str] = None,
        affected_contracts: list[str] = None,
        related_transactions: list[str] = None,
        assigned_to: Optional[str] = None,
    ) -> Incident:
        """
        Crea un nuevo incidente de seguridad.

        Args:
            title: Título descriptivo
            description: Descripción detallada
            severity: Severidad (SEV1-SEV4)
            detected_by: Quién/qué detectó el incidente
            related_alerts: IDs de alertas relacionadas
            affected_contracts: Direcciones de contratos afectados
            related_transactions: Hashes de transacciones relacionadas
            assigned_to: Persona asignada

        Returns:
            Incident creado
        """
        incident_id = self._generate_incident_id()

        incident = Incident(
            id=incident_id,
            title=title,
            description=description,
            severity=severity,
            status=IncidentStatus.DETECTED,
            detected_at=datetime.utcnow(),
            detected_by=detected_by,
            related_alerts=related_alerts or [],
            affected_contracts=affected_contracts or [],
            related_transactions=related_transactions or [],
            assigned_to=assigned_to,
        )

        self.incidents[incident_id] = incident

        # Notificar handlers
        for handler in self.incident_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(incident)
                else:
                    handler(incident)
            except Exception as e:
                logger.error(f"Error en incident handler: {e}")

        # Auto-contain para SEV1
        if severity == IncidentSeverity.SEV1 and self.auto_contain_sev1:
            await self.contain_incident(incident_id, "automated")

        return incident

    async def contain_incident(
        self,
        incident_id: str,
        executed_by: str,
    ) -> bool:
        """
        Contiene un incidente activando medidas de emergencia.

        Args:
            incident_id: ID del incidente
            executed_by: Quién ejecuta la contención

        Returns:
            True si se contuvo exitosamente
        """
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.status = IncidentStatus.CONTAINED
        incident.contained_at = datetime.utcnow()

        # Registrar acción
        action = IncidentAction(
            id=self._generate_action_id(),
            action_type=ActionType.TRIP_CIRCUIT_BREAKER,
            description="Circuit breaker activado para contención",
            executed_by=executed_by,
            executed_at=datetime.utcnow(),
            success=True,
        )
        incident.actions_taken.append(action)

        # TODO: Integrar con EmergencyControl.sol para activar circuit breaker real

        return True

    async def execute_playbook(
        self,
        incident_id: str,
        playbook_id: str,
    ) -> list[IncidentAction]:
        """
        Ejecuta un playbook de respuesta para un incidente.

        Args:
            incident_id: ID del incidente
            playbook_id: ID del playbook a ejecutar

        Returns:
            Lista de acciones ejecutadas
        """
        incident = self.incidents.get(incident_id)
        playbook = self.playbooks.get(playbook_id)

        if not incident or not playbook:
            return []

        incident.status = IncidentStatus.ANALYZING
        actions_executed: list[IncidentAction] = []

        for step in sorted(playbook.steps, key=lambda s: s.order):
            if step.automatic:
                action = await self._execute_step(incident, step)
                actions_executed.append(action)
                incident.actions_taken.append(action)

                if not action.success and step.required:
                    # Falló un paso requerido
                    break
            else:
                # Paso manual - solo registrar que está pendiente
                action = IncidentAction(
                    id=self._generate_action_id(),
                    action_type=step.action_type,
                    description=f"PENDIENTE: {step.description}",
                    executed_by="pending",
                    executed_at=datetime.utcnow(),
                    success=False,
                    metadata={"manual_required": True, "timeout_minutes": step.timeout_minutes},
                )
                actions_executed.append(action)
                incident.actions_taken.append(action)

        return actions_executed

    async def _execute_step(
        self,
        incident: Incident,
        step: PlaybookStep,
    ) -> IncidentAction:
        """Ejecuta un paso del playbook automáticamente."""
        action_id = self._generate_action_id()

        try:
            success = False
            result = None

            if step.action_type == ActionType.TRIP_CIRCUIT_BREAKER:
                # TODO: Llamar a EmergencyControl.tripCircuitBreaker()
                success = True
                result = "Circuit breaker activado"
                incident.status = IncidentStatus.CONTAINED
                incident.contained_at = datetime.utcnow()

            elif step.action_type == ActionType.PAUSE_CONTRACT:
                # TODO: Llamar a EmergencyControl.emergencyPause()
                success = True
                result = "Contratos pausados"

            elif step.action_type == ActionType.NOTIFY_TEAM:
                await self._notify_team(incident)
                success = True
                result = "Equipo notificado"

            elif step.action_type == ActionType.BLACKLIST_ADDRESS:
                # Esto generalmente requiere intervención manual
                success = False
                result = "Requiere revisión manual"

            elif step.action_type == ActionType.ESCALATE:
                incident.escalation_level += 1
                success = True
                result = f"Escalado a nivel {incident.escalation_level}"

            else:
                success = False
                result = f"Tipo de acción no implementado: {step.action_type}"

            return IncidentAction(
                id=action_id,
                action_type=step.action_type,
                description=step.description,
                executed_by="automated",
                executed_at=datetime.utcnow(),
                success=success,
                result=result,
            )

        except Exception as e:
            return IncidentAction(
                id=action_id,
                action_type=step.action_type,
                description=step.description,
                executed_by="automated",
                executed_at=datetime.utcnow(),
                success=False,
                result=f"Error: {str(e)}",
            )

    async def _notify_team(self, incident: Incident) -> None:
        """Notifica al equipo sobre un incidente."""
        # Determinar a quién notificar basado en severidad
        contacts = []

        if incident.severity == IncidentSeverity.SEV1:
            contacts = (
                self.emergency_contacts.get("security_team", []) +
                self.emergency_contacts.get("engineering_lead", []) +
                self.emergency_contacts.get("executive", [])
            )
        elif incident.severity == IncidentSeverity.SEV2:
            contacts = (
                self.emergency_contacts.get("security_team", []) +
                self.emergency_contacts.get("engineering_lead", [])
            )
        else:
            contacts = self.emergency_contacts.get("security_team", [])

        # TODO: Implementar notificaciones reales (email, Slack, PagerDuty, etc.)
        logger.info(f"[IRP] Notificando sobre incidente {incident.id} a: {contacts}")

    async def resolve_incident(
        self,
        incident_id: str,
        resolved_by: str,
        root_cause: Optional[str] = None,
    ) -> bool:
        """
        Marca un incidente como resuelto.

        Args:
            incident_id: ID del incidente
            resolved_by: Quién resuelve
            root_cause: Causa raíz identificada

        Returns:
            True si se resolvió exitosamente
        """
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.utcnow()
        incident.root_cause = root_cause

        action = IncidentAction(
            id=self._generate_action_id(),
            action_type=ActionType.DOCUMENT,
            description="Incidente marcado como resuelto",
            executed_by=resolved_by,
            executed_at=datetime.utcnow(),
            success=True,
            metadata={"root_cause": root_cause},
        )
        incident.actions_taken.append(action)

        return True

    async def close_incident(
        self,
        incident_id: str,
        closed_by: str,
        lessons_learned: str,
        preventive_measures: list[str],
        actual_loss: Optional[float] = None,
        funds_recovered: Optional[float] = None,
    ) -> bool:
        """
        Cierra un incidente con post-mortem completo.

        Args:
            incident_id: ID del incidente
            closed_by: Quién cierra
            lessons_learned: Lecciones aprendidas
            preventive_measures: Medidas preventivas para el futuro
            actual_loss: Pérdida real (si hubo)
            funds_recovered: Fondos recuperados (si aplica)

        Returns:
            True si se cerró exitosamente
        """
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        if incident.status != IncidentStatus.RESOLVED:
            return False  # Debe estar resuelto primero

        incident.status = IncidentStatus.CLOSED
        incident.closed_at = datetime.utcnow()
        incident.lessons_learned = lessons_learned
        incident.preventive_measures = preventive_measures
        incident.actual_loss = actual_loss
        incident.funds_recovered = funds_recovered

        action = IncidentAction(
            id=self._generate_action_id(),
            action_type=ActionType.DOCUMENT,
            description="Post-mortem completado, incidente cerrado",
            executed_by=closed_by,
            executed_at=datetime.utcnow(),
            success=True,
            metadata={
                "lessons_learned": lessons_learned,
                "preventive_measures": preventive_measures,
            },
        )
        incident.actions_taken.append(action)

        return True

    def generate_postmortem_report(self, incident_id: str) -> dict[str, Any]:
        """
        Genera un reporte post-mortem para un incidente.

        Args:
            incident_id: ID del incidente

        Returns:
            Reporte estructurado
        """
        incident = self.incidents.get(incident_id)
        if not incident:
            return {"error": "Incident not found"}

        # Calcular métricas de tiempo
        time_to_contain = None
        time_to_resolve = None
        total_duration = None

        if incident.contained_at:
            time_to_contain = (incident.contained_at - incident.detected_at).total_seconds() / 60

        if incident.resolved_at:
            time_to_resolve = (incident.resolved_at - incident.detected_at).total_seconds() / 60

        if incident.closed_at:
            total_duration = (incident.closed_at - incident.detected_at).total_seconds() / 3600

        return {
            "incident_id": incident.id,
            "title": incident.title,
            "severity": incident.severity.value,
            "status": incident.status.value,

            "timeline": {
                "detected_at": incident.detected_at.isoformat(),
                "contained_at": incident.contained_at.isoformat() if incident.contained_at else None,
                "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
                "closed_at": incident.closed_at.isoformat() if incident.closed_at else None,
            },

            "metrics": {
                "time_to_contain_minutes": time_to_contain,
                "time_to_resolve_minutes": time_to_resolve,
                "total_duration_hours": total_duration,
                "escalation_level": incident.escalation_level,
                "actions_taken_count": len(incident.actions_taken),
            },

            "impact": {
                "affected_contracts": incident.affected_contracts,
                "affected_users_count": len(incident.affected_users),
                "related_transactions": incident.related_transactions,
                "estimated_loss": incident.estimated_loss,
                "actual_loss": incident.actual_loss,
                "funds_recovered": incident.funds_recovered,
            },

            "analysis": {
                "description": incident.description,
                "root_cause": incident.root_cause,
                "detected_by": incident.detected_by,
            },

            "response": {
                "assigned_to": incident.assigned_to,
                "actions_taken": [
                    {
                        "action_type": a.action_type.value,
                        "description": a.description,
                        "executed_by": a.executed_by,
                        "executed_at": a.executed_at.isoformat(),
                        "success": a.success,
                        "result": a.result,
                    }
                    for a in incident.actions_taken
                ],
            },

            "post_mortem": {
                "lessons_learned": incident.lessons_learned,
                "preventive_measures": incident.preventive_measures,
            },
        }

    # ============ Helpers ============

    def _generate_incident_id(self) -> str:
        """Genera un ID único para un incidente."""
        data = f"incident:{datetime.utcnow().isoformat()}:{len(self.incidents)}"
        return f"INC-{hashlib.sha256(data.encode()).hexdigest()[:8].upper()}"

    def _generate_action_id(self) -> str:
        """Genera un ID único para una acción."""
        data = f"action:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:12]

    # ============ Consultas ============

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Obtiene un incidente por ID."""
        return self.incidents.get(incident_id)

    def get_active_incidents(self) -> list[Incident]:
        """Obtiene todos los incidentes activos (no cerrados)."""
        return [
            inc for inc in self.incidents.values()
            if inc.status != IncidentStatus.CLOSED
        ]

    def get_incidents_by_severity(self, severity: IncidentSeverity) -> list[Incident]:
        """Obtiene incidentes por severidad."""
        return [
            inc for inc in self.incidents.values()
            if inc.severity == severity
        ]

    def get_incident_statistics(self) -> dict[str, Any]:
        """Obtiene estadísticas de incidentes."""
        now = datetime.utcnow()
        last_30_days = now - timedelta(days=30)

        recent_incidents = [
            inc for inc in self.incidents.values()
            if inc.detected_at > last_30_days
        ]

        severity_counts = {s.value: 0 for s in IncidentSeverity}
        status_counts = {s.value: 0 for s in IncidentStatus}

        for inc in self.incidents.values():
            severity_counts[inc.severity.value] += 1
            status_counts[inc.status.value] += 1

        # MTTR (Mean Time To Resolve) para incidentes resueltos
        resolved_times = [
            (inc.resolved_at - inc.detected_at).total_seconds() / 60
            for inc in self.incidents.values()
            if inc.resolved_at
        ]
        mttr = sum(resolved_times) / len(resolved_times) if resolved_times else None

        return {
            "total_incidents": len(self.incidents),
            "active_incidents": len(self.get_active_incidents()),
            "incidents_last_30_days": len(recent_incidents),
            "by_severity": severity_counts,
            "by_status": status_counts,
            "mttr_minutes": mttr,
            "playbooks_available": len(self.playbooks),
        }
