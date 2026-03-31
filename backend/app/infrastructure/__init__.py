"""
Infraestructura de producción para FinCore.
Componentes críticos para operación en producción.
"""
from app.infrastructure.logging import (
    StructuredLogger,
    get_logger,
    correlation_id_var,
    set_correlation_id,
    get_correlation_id,
)
from app.infrastructure.secrets import SecretsManager, get_secret, get_secrets_manager
from app.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
    ServiceCircuitBreakers,
    stp_circuit_breaker,
    bitso_circuit_breaker,
    blockchain_circuit_breaker,
)
from app.infrastructure.alerting import AlertingService, AlertSeverity, alert_service
from app.infrastructure.waf import CloudflareWAF, WAFConfig
from app.infrastructure.degraded_mode import (
    DegradedModeManager,
    degraded_mode_manager,
    OperationalMode,
    ServiceStatus,
    requires_feature,
)

__all__ = [
    # Logging
    "StructuredLogger",
    "get_logger",
    "correlation_id_var",
    "set_correlation_id",
    "get_correlation_id",
    # Secrets
    "SecretsManager",
    "get_secret",
    "get_secrets_manager",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "CircuitState",
    "ServiceCircuitBreakers",
    "stp_circuit_breaker",
    "bitso_circuit_breaker",
    "blockchain_circuit_breaker",
    # Alerting
    "AlertingService",
    "AlertSeverity",
    "alert_service",
    # WAF
    "CloudflareWAF",
    "WAFConfig",
    # Degraded Mode
    "DegradedModeManager",
    "degraded_mode_manager",
    "OperationalMode",
    "ServiceStatus",
    "requires_feature",
]
