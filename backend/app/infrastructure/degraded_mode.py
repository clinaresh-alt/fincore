"""
Sistema de Modo Degradado para FinCore.
Permite operación parcial cuando servicios críticos no están disponibles.
"""
import logging
import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
import threading
import os

from app.infrastructure.logging import get_logger
from app.infrastructure.circuit_breaker import CircuitBreaker, CircuitState
from app.infrastructure.alerting import (
    AlertingService,
    Alert,
    AlertSeverity,
    alert_service,
)

logger = get_logger(__name__)


class ServiceStatus(Enum):
    """Estado de un servicio."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class OperationalMode(Enum):
    """Modos de operación del sistema."""
    NORMAL = "normal"  # Todas las funciones disponibles
    DEGRADED = "degraded"  # Funcionalidad reducida
    EMERGENCY = "emergency"  # Solo funciones críticas
    MAINTENANCE = "maintenance"  # En mantenimiento programado
    READONLY = "readonly"  # Solo lectura


@dataclass
class ServiceHealth:
    """Estado de salud de un servicio."""
    name: str
    status: ServiceStatus
    last_check: datetime
    last_success: Optional[datetime] = None
    error_message: Optional[str] = None
    consecutive_failures: int = 0
    response_time_ms: Optional[float] = None


@dataclass
class DegradedModeConfig:
    """Configuración del modo degradado."""
    # Umbrales para cambiar de modo
    degraded_threshold: int = 2  # Servicios fallando para entrar en degradado
    emergency_threshold: int = 4  # Servicios fallando para entrar en emergencia

    # Servicios críticos (si fallan = emergencia)
    critical_services: List[str] = field(default_factory=lambda: [
        "database",
        "redis",
    ])

    # Funciones deshabilitadas por modo
    disabled_features: Dict[str, List[str]] = field(default_factory=lambda: {
        "degraded": [
            "ai_analysis",
            "real_time_notifications",
            "market_data_streaming",
        ],
        "emergency": [
            "ai_analysis",
            "real_time_notifications",
            "market_data_streaming",
            "new_remittances",
            "trading",
            "blockchain_operations",
        ],
        "readonly": [
            "ai_analysis",
            "real_time_notifications",
            "market_data_streaming",
            "new_remittances",
            "trading",
            "blockchain_operations",
            "create_users",
            "update_settings",
        ],
    })

    # Auto-recovery
    auto_recover: bool = True
    recovery_check_interval_seconds: int = 30


class DegradedModeManager:
    """
    Gestor del modo degradado.

    Monitorea servicios y activa/desactiva funciones según disponibilidad.
    """

    _instance: Optional["DegradedModeManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[DegradedModeConfig] = None):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.config = config or DegradedModeConfig()
        self._mode = OperationalMode.NORMAL
        self._services: Dict[str, ServiceHealth] = {}
        self._disabled_features: Set[str] = set()
        self._mode_change_time: datetime = datetime.utcnow()
        self._alerting = alert_service
        self._check_task: Optional[asyncio.Task] = None
        self._initialized = True

        logger.info("DegradedModeManager initialized")

    @property
    def mode(self) -> OperationalMode:
        """Modo operacional actual."""
        return self._mode

    @property
    def is_degraded(self) -> bool:
        """Indica si el sistema está en modo degradado o peor."""
        return self._mode in (
            OperationalMode.DEGRADED,
            OperationalMode.EMERGENCY,
            OperationalMode.READONLY,
        )

    @property
    def services(self) -> Dict[str, ServiceHealth]:
        """Estado de todos los servicios monitoreados."""
        return self._services.copy()

    def is_feature_enabled(self, feature: str) -> bool:
        """Verifica si una función está habilitada."""
        return feature not in self._disabled_features

    def register_service(
        self,
        name: str,
        health_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Registra un servicio para monitoreo."""
        self._services[name] = ServiceHealth(
            name=name,
            status=ServiceStatus.UNKNOWN,
            last_check=datetime.utcnow(),
        )
        logger.info(f"Service registered: {name}")

    def update_service_health(
        self,
        name: str,
        status: ServiceStatus,
        error_message: Optional[str] = None,
        response_time_ms: Optional[float] = None,
    ) -> None:
        """Actualiza el estado de un servicio."""
        now = datetime.utcnow()

        if name not in self._services:
            self._services[name] = ServiceHealth(
                name=name,
                status=status,
                last_check=now,
            )

        service = self._services[name]
        old_status = service.status

        service.status = status
        service.last_check = now
        service.error_message = error_message
        service.response_time_ms = response_time_ms

        if status == ServiceStatus.HEALTHY:
            service.last_success = now
            service.consecutive_failures = 0
        else:
            service.consecutive_failures += 1

        # Log cambio de estado
        if old_status != status:
            logger.warning(
                f"Service '{name}' status changed: {old_status.value} -> {status.value}",
                service=name,
                old_status=old_status.value,
                new_status=status.value,
                error=error_message,
            )

        # Re-evaluar modo del sistema
        self._evaluate_mode()

    def _evaluate_mode(self) -> None:
        """Evalúa y actualiza el modo operacional."""
        unhealthy_services = [
            s for s in self._services.values()
            if s.status != ServiceStatus.HEALTHY
        ]

        unhealthy_critical = [
            s for s in unhealthy_services
            if s.name in self.config.critical_services
        ]

        old_mode = self._mode

        # Determinar nuevo modo
        if unhealthy_critical:
            new_mode = OperationalMode.EMERGENCY
        elif len(unhealthy_services) >= self.config.emergency_threshold:
            new_mode = OperationalMode.EMERGENCY
        elif len(unhealthy_services) >= self.config.degraded_threshold:
            new_mode = OperationalMode.DEGRADED
        else:
            new_mode = OperationalMode.NORMAL

        # Actualizar si cambió
        if new_mode != old_mode:
            self._set_mode(new_mode)

    def _set_mode(self, mode: OperationalMode) -> None:
        """Cambia el modo operacional."""
        old_mode = self._mode
        self._mode = mode
        self._mode_change_time = datetime.utcnow()

        # Actualizar features deshabilitadas
        self._disabled_features.clear()
        mode_key = mode.value
        if mode_key in self.config.disabled_features:
            self._disabled_features.update(
                self.config.disabled_features[mode_key]
            )

        logger.critical(
            f"Operational mode changed: {old_mode.value} -> {mode.value}",
            old_mode=old_mode.value,
            new_mode=mode.value,
            disabled_features=list(self._disabled_features),
        )

        # Enviar alerta
        asyncio.create_task(self._send_mode_change_alert(old_mode, mode))

    async def _send_mode_change_alert(
        self,
        old_mode: OperationalMode,
        new_mode: OperationalMode,
    ) -> None:
        """Envía alerta de cambio de modo."""
        severity = (
            AlertSeverity.CRITICAL
            if new_mode in (OperationalMode.EMERGENCY, OperationalMode.READONLY)
            else AlertSeverity.WARNING
            if new_mode == OperationalMode.DEGRADED
            else AlertSeverity.INFO
        )

        unhealthy = [
            s.name for s in self._services.values()
            if s.status != ServiceStatus.HEALTHY
        ]

        alert = Alert(
            title=f"System Mode Changed: {new_mode.value.upper()}",
            description=(
                f"FinCore operational mode changed from {old_mode.value} to {new_mode.value}. "
                f"Unhealthy services: {', '.join(unhealthy) or 'none'}."
            ),
            severity=severity,
            source="fincore-degraded-mode",
            component="system",
            group="infrastructure",
            class_type="mode_change",
            custom_details={
                "old_mode": old_mode.value,
                "new_mode": new_mode.value,
                "unhealthy_services": unhealthy,
                "disabled_features": list(self._disabled_features),
            },
        )

        await self._alerting.send_alert(alert)

    def force_mode(self, mode: OperationalMode) -> None:
        """Fuerza un modo específico (para mantenimiento)."""
        logger.warning(f"Forcing operational mode: {mode.value}")
        self._set_mode(mode)

    def get_status(self) -> Dict[str, Any]:
        """Obtiene estado completo del sistema."""
        return {
            "mode": self._mode.value,
            "mode_since": self._mode_change_time.isoformat(),
            "is_degraded": self.is_degraded,
            "services": {
                name: {
                    "status": s.status.value,
                    "last_check": s.last_check.isoformat(),
                    "last_success": s.last_success.isoformat() if s.last_success else None,
                    "consecutive_failures": s.consecutive_failures,
                    "response_time_ms": s.response_time_ms,
                    "error": s.error_message,
                }
                for name, s in self._services.items()
            },
            "disabled_features": list(self._disabled_features),
            "healthy_services": sum(
                1 for s in self._services.values()
                if s.status == ServiceStatus.HEALTHY
            ),
            "total_services": len(self._services),
        }

    async def start_health_checks(self) -> None:
        """Inicia el loop de health checks automático."""
        if self._check_task and not self._check_task.done():
            return

        self._check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Health check loop started")

    async def stop_health_checks(self) -> None:
        """Detiene el loop de health checks."""
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
            self._check_task = None
            logger.info("Health check loop stopped")

    async def _health_check_loop(self) -> None:
        """Loop de health checks."""
        while True:
            try:
                # Verificar circuit breakers
                cb_stats = CircuitBreaker.get_all_stats()
                for name, stats in cb_stats.items():
                    if name in self._services:
                        status = (
                            ServiceStatus.HEALTHY
                            if stats["state"] == "closed"
                            else ServiceStatus.DEGRADED
                            if stats["state"] == "half_open"
                            else ServiceStatus.UNAVAILABLE
                        )
                        self.update_service_health(name, status)

                await asyncio.sleep(self.config.recovery_check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(10)


# Singleton global
degraded_mode_manager = DegradedModeManager()


# Decorator para verificar si una función está habilitada
def requires_feature(feature: str):
    """Decorator que verifica si una feature está habilitada."""

    def decorator(func: Callable):
        async def async_wrapper(*args, **kwargs):
            if not degraded_mode_manager.is_feature_enabled(feature):
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "feature_unavailable",
                        "feature": feature,
                        "mode": degraded_mode_manager.mode.value,
                        "message": f"Feature '{feature}' is temporarily unavailable",
                    },
                )
            return await func(*args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            if not degraded_mode_manager.is_feature_enabled(feature):
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "feature_unavailable",
                        "feature": feature,
                        "mode": degraded_mode_manager.mode.value,
                    },
                )
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
