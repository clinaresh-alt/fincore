"""
Servicios de Auditoria de Smart Contracts.

Incluye:
- SlitherAuditService: Analisis estatico con Slither
- TransactionMonitoringService: Monitoreo de transacciones
- IncidentResponseService: Gestion de incidentes (IRP)
"""

import asyncio
import subprocess
import json
import hashlib
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4
from dataclasses import dataclass, field


# ============ Enums ============


class AlertSeverity(Enum):
    """Severidad de alertas."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertType(Enum):
    """Tipos de alerta."""
    HIGH_VALUE_TRANSFER = "high_value_transfer"
    UNUSUAL_GAS = "unusual_gas"
    BLACKLISTED_ADDRESS = "blacklisted_address"
    RAPID_TRANSACTIONS = "rapid_transactions"
    FLASH_LOAN = "flash_loan"
    REENTRANCY_PATTERN = "reentrancy_pattern"
    CONTRACT_INTERACTION = "contract_interaction"


class IncidentSeverity(Enum):
    """Severidad de incidentes."""
    SEV1 = "sev1"  # Critico - perdida de fondos
    SEV2 = "sev2"  # Alto - vulnerabilidad explotable
    SEV3 = "sev3"  # Medio - anomalia detectada
    SEV4 = "sev4"  # Bajo - informacional


class IncidentStatus(Enum):
    """Estado de incidentes."""
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    RESOLVED = "resolved"


# ============ Dataclasses ============


@dataclass
class Alert:
    """Alerta de seguridad."""
    id: str
    type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    transaction_hash: Optional[str] = None
    contract_address: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None


@dataclass
class Incident:
    """Incidente de seguridad."""
    id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    detected_at: datetime
    detected_by: str
    affected_contracts: list[str] = field(default_factory=list)
    related_transactions: list[str] = field(default_factory=list)
    related_alerts: list[str] = field(default_factory=list)
    actions_taken: list[dict] = field(default_factory=list)
    contained_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    root_cause: Optional[str] = None


@dataclass
class MonitoringRule:
    """Regla de monitoreo."""
    id: str
    name: str
    description: str
    alert_type: AlertType
    severity: AlertSeverity
    threshold: Decimal
    enabled: bool = True


# ============ SlitherAuditService ============


class SlitherAuditService:
    """
    Servicio de auditoria con Slither.

    Ejecuta analisis estatico de smart contracts
    y genera reportes de vulnerabilidades.
    """

    # Detectores de Slither organizados por severidad
    HIGH_DETECTORS = [
        "reentrancy-eth",
        "reentrancy-no-eth",
        "unprotected-upgrade",
        "arbitrary-send-eth",
        "arbitrary-send-erc20",
        "suicidal",
        "controlled-delegatecall",
    ]

    MEDIUM_DETECTORS = [
        "locked-ether",
        "incorrect-equality",
        "reentrancy-events",
        "tx-origin",
        "uninitialized-state",
        "unused-return",
    ]

    LOW_DETECTORS = [
        "naming-convention",
        "solc-version",
        "missing-zero-check",
        "reentrancy-benign",
    ]

    def __init__(self):
        """Inicializa el servicio."""
        self._slither_path = "slither"
        self._audit_cache: dict[str, dict] = {}

    def is_slither_installed(self) -> bool:
        """Verifica si Slither esta instalado."""
        try:
            result = subprocess.run(
                [self._slither_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def list_detectors(self) -> list[dict]:
        """Lista todos los detectores disponibles."""
        return [
            {"category": "high", "detectors": self.HIGH_DETECTORS},
            {"category": "medium", "detectors": self.MEDIUM_DETECTORS},
            {"category": "low", "detectors": self.LOW_DETECTORS},
        ]

    async def audit_contract(
        self,
        contract_path: str,
        generate_html: bool = True,
    ) -> dict:
        """
        Ejecuta auditoria completa de un contrato.

        Args:
            contract_path: Ruta al archivo .sol
            generate_html: Si generar reporte HTML

        Returns:
            Diccionario con resultados de auditoria
        """
        # Verificar cache
        cache_key = hashlib.md5(contract_path.encode()).hexdigest()
        if cache_key in self._audit_cache:
            cached = self._audit_cache[cache_key]
            # Cache valido por 1 hora
            if (datetime.utcnow() - datetime.fromisoformat(cached["timestamp"])).seconds < 3600:
                return cached

        # Ejecutar Slither
        result = await self._run_slither(contract_path)

        # Procesar resultados
        vulnerabilities = self._parse_slither_output(result)

        # Calcular score de seguridad
        security_score = self._calculate_security_score(vulnerabilities)

        # Generar recomendaciones
        recommendations = self._generate_recommendations(vulnerabilities)

        audit_result = {
            "contract_path": contract_path,
            "timestamp": datetime.utcnow().isoformat(),
            "security_score": security_score,
            "vulnerabilities_count": {
                "high": vulnerabilities.get("high", 0),
                "medium": vulnerabilities.get("medium", 0),
                "low": vulnerabilities.get("low", 0),
                "informational": vulnerabilities.get("informational", 0),
            },
            "high_severity_issues": vulnerabilities.get("high_issues", []),
            "recommendations": recommendations,
        }

        if generate_html:
            html_path = await self._generate_html_report(contract_path, audit_result)
            audit_result["html_report_path"] = html_path

        # Guardar en cache
        self._audit_cache[cache_key] = audit_result

        return audit_result

    async def _run_slither(self, contract_path: str) -> dict:
        """Ejecuta Slither en el contrato."""
        cmd = [
            self._slither_path,
            contract_path,
            "--json", "-"
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if stdout:
            try:
                return json.loads(stdout.decode())
            except json.JSONDecodeError:
                return {"results": {"detectors": []}}

        return {"results": {"detectors": []}}

    def _parse_slither_output(self, output: dict) -> dict:
        """Parsea la salida de Slither."""
        detectors = output.get("results", {}).get("detectors", [])

        high_count = 0
        medium_count = 0
        low_count = 0
        info_count = 0
        high_issues = []

        for detector in detectors:
            impact = detector.get("impact", "").lower()

            if impact in ["high", "critical"]:
                high_count += 1
                high_issues.append({
                    "type": detector.get("check", "unknown"),
                    "description": detector.get("description", ""),
                    "location": detector.get("elements", [{}])[0].get("source_mapping", {}).get("filename_short", "unknown"),
                })
            elif impact == "medium":
                medium_count += 1
            elif impact == "low":
                low_count += 1
            else:
                info_count += 1

        return {
            "high": high_count,
            "medium": medium_count,
            "low": low_count,
            "informational": info_count,
            "high_issues": high_issues,
        }

    def _calculate_security_score(self, vulnerabilities: dict) -> int:
        """Calcula el score de seguridad (0-100)."""
        base_score = 100

        # Penalizaciones por tipo
        base_score -= vulnerabilities.get("high", 0) * 20
        base_score -= vulnerabilities.get("medium", 0) * 10
        base_score -= vulnerabilities.get("low", 0) * 5
        base_score -= vulnerabilities.get("informational", 0) * 1

        return max(0, min(100, base_score))

    def _generate_recommendations(self, vulnerabilities: dict) -> list[str]:
        """Genera recomendaciones basadas en vulnerabilidades."""
        recommendations = []

        if vulnerabilities.get("high", 0) > 0:
            recommendations.append("CRITICO: Revisar y corregir todas las vulnerabilidades de alta severidad antes de deployment")
            recommendations.append("Considerar una auditoria externa profesional")

        if vulnerabilities.get("medium", 0) > 0:
            recommendations.append("Revisar patrones de codigo que puedan llevar a comportamiento inesperado")

        if vulnerabilities.get("low", 0) > 0:
            recommendations.append("Mejorar practicas de codigo siguiendo estandares de Solidity")

        # Recomendaciones generales
        recommendations.extend([
            "Implementar tests unitarios con cobertura >90%",
            "Usar OpenZeppelin para funciones estandar",
            "Implementar circuit breaker para emergencias",
        ])

        return recommendations

    async def _generate_html_report(self, contract_path: str, audit_result: dict) -> str:
        """Genera reporte HTML."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_path = f"/tmp/audit_report_{timestamp}.html"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Audit Report - {contract_path}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .score {{ font-size: 48px; font-weight: bold; }}
                .high {{ color: #dc2626; }}
                .medium {{ color: #f59e0b; }}
                .low {{ color: #3b82f6; }}
            </style>
        </head>
        <body>
            <h1>Security Audit Report</h1>
            <p><strong>Contract:</strong> {contract_path}</p>
            <p><strong>Date:</strong> {audit_result['timestamp']}</p>
            <p class="score">Security Score: {audit_result['security_score']}/100</p>

            <h2>Vulnerabilities</h2>
            <ul>
                <li class="high">High: {audit_result['vulnerabilities_count']['high']}</li>
                <li class="medium">Medium: {audit_result['vulnerabilities_count']['medium']}</li>
                <li class="low">Low: {audit_result['vulnerabilities_count']['low']}</li>
                <li>Informational: {audit_result['vulnerabilities_count']['informational']}</li>
            </ul>

            <h2>Recommendations</h2>
            <ul>
                {''.join(f'<li>{r}</li>' for r in audit_result['recommendations'])}
            </ul>
        </body>
        </html>
        """

        with open(report_path, 'w') as f:
            f.write(html_content)

        return report_path


# ============ TransactionMonitoringService ============


class TransactionMonitoringService:
    """
    Servicio de monitoreo de transacciones.

    Analiza transacciones en tiempo real para detectar
    actividad sospechosa basada en reglas configurables.
    """

    # Umbrales por defecto
    DEFAULT_HIGH_VALUE_THRESHOLD = Decimal("10000")  # USD
    DEFAULT_GAS_MULTIPLIER = Decimal("3")  # 3x el gas promedio

    # Direcciones en blacklist (ejemplo)
    BLACKLISTED_ADDRESSES = {
        "0x0000000000000000000000000000000000000000",  # Ejemplo
    }

    def __init__(self):
        """Inicializa el servicio de monitoreo."""
        self.alerts: list[Alert] = []
        self.rules: list[MonitoringRule] = self._initialize_default_rules()
        self._transaction_history: dict[str, list[datetime]] = {}

    def _initialize_default_rules(self) -> list[MonitoringRule]:
        """Inicializa reglas por defecto."""
        return [
            MonitoringRule(
                id="rule_high_value",
                name="High Value Transfer",
                description="Detecta transferencias de alto valor",
                alert_type=AlertType.HIGH_VALUE_TRANSFER,
                severity=AlertSeverity.HIGH,
                threshold=self.DEFAULT_HIGH_VALUE_THRESHOLD,
            ),
            MonitoringRule(
                id="rule_unusual_gas",
                name="Unusual Gas Price",
                description="Detecta precios de gas inusuales",
                alert_type=AlertType.UNUSUAL_GAS,
                severity=AlertSeverity.MEDIUM,
                threshold=self.DEFAULT_GAS_MULTIPLIER,
            ),
            MonitoringRule(
                id="rule_rapid_tx",
                name="Rapid Transactions",
                description="Detecta multiples transacciones rapidas",
                alert_type=AlertType.RAPID_TRANSACTIONS,
                severity=AlertSeverity.MEDIUM,
                threshold=Decimal("5"),  # 5 tx en 1 minuto
            ),
        ]

    async def analyze_transaction(
        self,
        tx_hash: str,
        from_address: str,
        to_address: str,
        value: Decimal,
        gas_price: int,
        input_data: str = "0x",
        network: str = "ethereum",
    ) -> list[Alert]:
        """
        Analiza una transaccion para detectar actividad sospechosa.

        Args:
            tx_hash: Hash de la transaccion
            from_address: Direccion origen
            to_address: Direccion destino
            value: Valor transferido
            gas_price: Precio de gas
            input_data: Datos de input
            network: Red blockchain

        Returns:
            Lista de alertas generadas
        """
        generated_alerts = []

        # Verificar direcciones en blacklist
        if from_address.lower() in self.BLACKLISTED_ADDRESSES or \
           to_address.lower() in self.BLACKLISTED_ADDRESSES:
            alert = Alert(
                id=str(uuid4()),
                type=AlertType.BLACKLISTED_ADDRESS,
                severity=AlertSeverity.CRITICAL,
                title="Blacklisted Address Detected",
                description=f"Transaction involves blacklisted address",
                transaction_hash=tx_hash,
            )
            generated_alerts.append(alert)
            self.alerts.append(alert)

        # Verificar alto valor
        for rule in self.rules:
            if not rule.enabled:
                continue

            if rule.alert_type == AlertType.HIGH_VALUE_TRANSFER:
                if value >= rule.threshold:
                    alert = Alert(
                        id=str(uuid4()),
                        type=AlertType.HIGH_VALUE_TRANSFER,
                        severity=rule.severity,
                        title="High Value Transfer Detected",
                        description=f"Transfer of {value} detected (threshold: {rule.threshold})",
                        transaction_hash=tx_hash,
                    )
                    generated_alerts.append(alert)
                    self.alerts.append(alert)

            elif rule.alert_type == AlertType.UNUSUAL_GAS:
                avg_gas = 30_000_000_000  # 30 Gwei promedio
                if gas_price > avg_gas * float(rule.threshold):
                    alert = Alert(
                        id=str(uuid4()),
                        type=AlertType.UNUSUAL_GAS,
                        severity=rule.severity,
                        title="Unusual Gas Price Detected",
                        description=f"Gas price {gas_price} is {gas_price / avg_gas:.1f}x average",
                        transaction_hash=tx_hash,
                    )
                    generated_alerts.append(alert)
                    self.alerts.append(alert)

            elif rule.alert_type == AlertType.RAPID_TRANSACTIONS:
                # Rastrear transacciones por direccion
                now = datetime.utcnow()
                key = from_address.lower()

                if key not in self._transaction_history:
                    self._transaction_history[key] = []

                # Limpiar transacciones viejas (>1 minuto)
                self._transaction_history[key] = [
                    ts for ts in self._transaction_history[key]
                    if (now - ts).seconds < 60
                ]

                self._transaction_history[key].append(now)

                if len(self._transaction_history[key]) >= int(rule.threshold):
                    alert = Alert(
                        id=str(uuid4()),
                        type=AlertType.RAPID_TRANSACTIONS,
                        severity=rule.severity,
                        title="Rapid Transactions Detected",
                        description=f"{len(self._transaction_history[key])} transactions in last minute from {from_address[:10]}...",
                        transaction_hash=tx_hash,
                    )
                    generated_alerts.append(alert)
                    self.alerts.append(alert)

        # Detectar patrones de reentrancia
        if self._detect_reentrancy_pattern(input_data):
            alert = Alert(
                id=str(uuid4()),
                type=AlertType.REENTRANCY_PATTERN,
                severity=AlertSeverity.CRITICAL,
                title="Possible Reentrancy Pattern",
                description="Transaction input data matches reentrancy attack pattern",
                transaction_hash=tx_hash,
            )
            generated_alerts.append(alert)
            self.alerts.append(alert)

        return generated_alerts

    def _detect_reentrancy_pattern(self, input_data: str) -> bool:
        """Detecta patrones de reentrancia en input data."""
        # Patrones sospechosos (simplificado)
        suspicious_patterns = [
            "0x3ccfd60b",  # withdraw()
            "0x2e1a7d4d",  # withdraw(uint256)
        ]

        return any(pattern in input_data.lower() for pattern in suspicious_patterns)

    def get_recent_alerts(
        self,
        limit: int = 50,
        severity: Optional[AlertSeverity] = None,
    ) -> list[Alert]:
        """Obtiene alertas recientes."""
        alerts = self.alerts

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)[:limit]

    def acknowledge_alert(self, alert_id: str, user: str = "system") -> bool:
        """Reconoce una alerta."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_by = user
                alert.acknowledged_at = datetime.utcnow()
                return True
        return False

    def get_alert_statistics(self) -> dict:
        """Obtiene estadisticas de alertas."""
        total = len(self.alerts)
        acknowledged = sum(1 for a in self.alerts if a.acknowledged)

        by_severity = {}
        for severity in AlertSeverity:
            by_severity[severity.value] = sum(
                1 for a in self.alerts if a.severity == severity
            )

        by_type = {}
        for alert_type in AlertType:
            by_type[alert_type.value] = sum(
                1 for a in self.alerts if a.type == alert_type
            )

        return {
            "total_alerts": total,
            "acknowledged": acknowledged,
            "unacknowledged": total - acknowledged,
            "by_severity": by_severity,
            "by_type": by_type,
        }

    def add_rule(self, rule: MonitoringRule) -> None:
        """Agrega una regla de monitoreo."""
        self.rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """Elimina una regla de monitoreo."""
        for i, rule in enumerate(self.rules):
            if rule.id == rule_id:
                self.rules.pop(i)
                return True
        return False


# ============ IncidentResponseService ============


class IncidentResponseService:
    """
    Servicio de respuesta a incidentes (IRP).

    Gestiona el ciclo de vida de incidentes de seguridad:
    deteccion -> contencion -> resolucion -> post-mortem.
    """

    def __init__(self, monitoring_service: TransactionMonitoringService):
        """
        Inicializa el servicio IRP.

        Args:
            monitoring_service: Servicio de monitoreo para correlacionar alertas
        """
        self.monitoring = monitoring_service
        self.incidents: dict[str, Incident] = {}
        self._circuit_breaker_active = False

    async def create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        detected_by: str,
        affected_contracts: list[str] = None,
        related_transactions: list[str] = None,
    ) -> Incident:
        """
        Crea un nuevo incidente.

        Args:
            title: Titulo del incidente
            description: Descripcion detallada
            severity: Severidad (SEV1-SEV4)
            detected_by: Usuario que detecta
            affected_contracts: Lista de contratos afectados
            related_transactions: Lista de transacciones relacionadas

        Returns:
            Incidente creado
        """
        incident_id = str(uuid4())

        incident = Incident(
            id=incident_id,
            title=title,
            description=description,
            severity=severity,
            status=IncidentStatus.DETECTED,
            detected_at=datetime.utcnow(),
            detected_by=detected_by,
            affected_contracts=affected_contracts or [],
            related_transactions=related_transactions or [],
        )

        # Registrar accion inicial
        incident.actions_taken.append({
            "action": "incident_created",
            "timestamp": datetime.utcnow().isoformat(),
            "by": detected_by,
        })

        # Para SEV1, activar circuit breaker automaticamente
        if severity == IncidentSeverity.SEV1:
            await self._activate_circuit_breaker(incident)

        self.incidents[incident_id] = incident

        return incident

    async def _activate_circuit_breaker(self, incident: Incident) -> None:
        """Activa el circuit breaker de emergencia."""
        self._circuit_breaker_active = True

        incident.actions_taken.append({
            "action": "circuit_breaker_activated",
            "timestamp": datetime.utcnow().isoformat(),
            "by": "system",
            "reason": "SEV1 incident auto-response",
        })

        # En produccion, esto pausaria los contratos
        # await self._pause_affected_contracts(incident.affected_contracts)

    async def contain_incident(self, incident_id: str, contained_by: str) -> bool:
        """
        Marca un incidente como contenido.

        Args:
            incident_id: ID del incidente
            contained_by: Usuario que contiene

        Returns:
            True si exitoso
        """
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.status = IncidentStatus.CONTAINED
        incident.contained_at = datetime.utcnow()

        incident.actions_taken.append({
            "action": "incident_contained",
            "timestamp": datetime.utcnow().isoformat(),
            "by": contained_by,
        })

        return True

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
            resolved_by: Usuario que resuelve
            root_cause: Causa raiz identificada

        Returns:
            True si exitoso
        """
        incident = self.incidents.get(incident_id)
        if not incident:
            return False

        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.utcnow()
        incident.root_cause = root_cause

        incident.actions_taken.append({
            "action": "incident_resolved",
            "timestamp": datetime.utcnow().isoformat(),
            "by": resolved_by,
            "root_cause": root_cause,
        })

        # Desactivar circuit breaker si estaba activo
        if incident.severity == IncidentSeverity.SEV1:
            self._circuit_breaker_active = False
            incident.actions_taken.append({
                "action": "circuit_breaker_deactivated",
                "timestamp": datetime.utcnow().isoformat(),
                "by": "system",
            })

        return True

    def get_active_incidents(self) -> list[Incident]:
        """Obtiene incidentes activos (no resueltos)."""
        return [
            inc for inc in self.incidents.values()
            if inc.status != IncidentStatus.RESOLVED
        ]

    def get_incident_statistics(self) -> dict:
        """Obtiene estadisticas de incidentes."""
        incidents = list(self.incidents.values())

        by_severity = {}
        for severity in IncidentSeverity:
            by_severity[severity.value] = sum(
                1 for i in incidents if i.severity == severity
            )

        by_status = {}
        for status in IncidentStatus:
            by_status[status.value] = sum(
                1 for i in incidents if i.status == status
            )

        # Calcular MTTR (Mean Time To Resolve)
        resolved = [i for i in incidents if i.resolved_at]
        if resolved:
            total_resolution_time = sum(
                (i.resolved_at - i.detected_at).seconds
                for i in resolved
            )
            mttr_seconds = total_resolution_time / len(resolved)
        else:
            mttr_seconds = 0

        return {
            "total_incidents": len(incidents),
            "active_incidents": len(self.get_active_incidents()),
            "circuit_breaker_active": self._circuit_breaker_active,
            "by_severity": by_severity,
            "by_status": by_status,
            "mttr_seconds": mttr_seconds,
        }

    def generate_postmortem_report(self, incident_id: str) -> dict:
        """
        Genera reporte post-mortem de un incidente.

        Args:
            incident_id: ID del incidente

        Returns:
            Reporte post-mortem
        """
        incident = self.incidents.get(incident_id)
        if not incident:
            return {"error": f"Incident not found: {incident_id}"}

        # Calcular tiempos
        detection_time = incident.detected_at
        containment_time = incident.contained_at
        resolution_time = incident.resolved_at

        time_to_contain = None
        time_to_resolve = None

        if containment_time:
            time_to_contain = (containment_time - detection_time).seconds

        if resolution_time:
            time_to_resolve = (resolution_time - detection_time).seconds

        return {
            "incident_id": incident.id,
            "title": incident.title,
            "severity": incident.severity.value,
            "status": incident.status.value,
            "timeline": {
                "detected_at": detection_time.isoformat(),
                "contained_at": containment_time.isoformat() if containment_time else None,
                "resolved_at": resolution_time.isoformat() if resolution_time else None,
            },
            "metrics": {
                "time_to_contain_seconds": time_to_contain,
                "time_to_resolve_seconds": time_to_resolve,
            },
            "root_cause": incident.root_cause,
            "affected_contracts": incident.affected_contracts,
            "related_transactions": incident.related_transactions,
            "actions_taken": incident.actions_taken,
            "recommendations": self._generate_postmortem_recommendations(incident),
        }

    def _generate_postmortem_recommendations(self, incident: Incident) -> list[str]:
        """Genera recomendaciones para el post-mortem."""
        recommendations = []

        if incident.severity in [IncidentSeverity.SEV1, IncidentSeverity.SEV2]:
            recommendations.append("Considerar auditoria de seguridad externa")
            recommendations.append("Revisar controles de acceso en contratos afectados")

        # Tiempo de contencion largo
        if incident.contained_at and incident.detected_at:
            ttc = (incident.contained_at - incident.detected_at).seconds
            if ttc > 3600:  # Mas de 1 hora
                recommendations.append("Mejorar playbooks de respuesta para reducir tiempo de contencion")

        recommendations.append("Actualizar documentacion de seguridad")
        recommendations.append("Realizar sesion de lessons learned con el equipo")

        return recommendations
