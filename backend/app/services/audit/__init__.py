"""
Sistema de Auditoría Automática de Smart Contracts para FinCore.

Arquitectura de Seguridad Multicapa:
====================================

1. PRE-DEPLOYMENT (CI/CD):
   - Slither: Análisis estático (70+ detectores de vulnerabilidades)
   - Mythril: Ejecución simbólica (análisis de estados)
   - Echidna: Fuzzing basado en propiedades

2. RUNTIME (Monitoreo en Tiempo Real):
   - TransactionMonitoringService: Detección de patrones sospechosos
   - Integración con Tenderly/Forta para alertas
   - Reglas de monitoreo personalizables

3. EMERGENCY RESPONSE:
   - EmergencyControl.sol: Circuit Breaker en cadena
   - IncidentResponseService: Plan de Respuesta ante Incidentes (IRP)
   - Playbooks automáticos para diferentes tipos de ataques

4. POST-INCIDENT:
   - Generación de reportes post-mortem
   - Análisis de causa raíz
   - Métricas (MTTR, MTTD)

Uso:
----
    from app.services.audit import (
        SlitherAuditService,
        TransactionMonitoringService,
        IncidentResponseService,
    )

    # Auditoría pre-deployment
    slither = SlitherAuditService()
    report = await slither.audit_contract("contracts/MyToken.sol")

    # Monitoreo runtime
    monitor = TransactionMonitoringService()
    alerts = await monitor.analyze_transaction(tx_hash, from_addr, ...)

    # Respuesta a incidentes
    irp = IncidentResponseService(monitor)
    incident = await irp.create_incident(title, description, severity)
"""

from app.services.audit.slither_service import SlitherAuditService
from app.services.audit.monitoring_service import (
    TransactionMonitoringService,
    Alert,
    AlertSeverity,
    AlertType,
    MonitoringRule,
)
from app.services.audit.incident_response import (
    IncidentResponseService,
    Incident,
    IncidentStatus,
    IncidentSeverity,
    ResponsePlaybook,
)

__all__ = [
    # Servicios principales
    "SlitherAuditService",
    "TransactionMonitoringService",
    "IncidentResponseService",

    # Modelos de monitoreo
    "Alert",
    "AlertSeverity",
    "AlertType",
    "MonitoringRule",

    # Modelos de IRP
    "Incident",
    "IncidentStatus",
    "IncidentSeverity",
    "ResponsePlaybook",
]
