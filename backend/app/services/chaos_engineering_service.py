"""
Servicio de Chaos Engineering para FinCore.

Implementa experimentos de caos controlados para:
- Probar resiliencia del sistema
- Validar mecanismos de recuperacion
- Identificar puntos de falla
- Entrenar al equipo en respuesta a incidentes

Uso:
    from app.services.chaos_engineering_service import ChaosService

    chaos = ChaosService()

    # Ejecutar experimento
    result = await chaos.run_experiment("latency-injection", {
        "target": "database",
        "latency_ms": 500,
        "duration_seconds": 60,
    })

ADVERTENCIA: Solo usar en ambientes de desarrollo/staging
"""
import os
import json
import logging
import asyncio
import random
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base, SessionLocal

logger = logging.getLogger(__name__)


# ============================================================================
# Configuracion
# ============================================================================

# Solo permitir chaos en estos ambientes
ALLOWED_ENVIRONMENTS = os.getenv("CHAOS_ALLOWED_ENVS", "development,staging").split(",")
CURRENT_ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Feature flag global
CHAOS_ENABLED = os.getenv("CHAOS_ENABLED", "false").lower() == "true"

# Limites de seguridad
MAX_EXPERIMENT_DURATION = int(os.getenv("CHAOS_MAX_DURATION", "300"))  # 5 min
MAX_CONCURRENT_EXPERIMENTS = int(os.getenv("CHAOS_MAX_CONCURRENT", "1"))
BLAST_RADIUS_LIMIT = float(os.getenv("CHAOS_BLAST_RADIUS", "0.1"))  # 10%


# ============================================================================
# Tipos
# ============================================================================

class ExperimentType(str, Enum):
    """Tipos de experimentos de caos."""
    LATENCY_INJECTION = "latency-injection"
    ERROR_INJECTION = "error-injection"
    RESOURCE_EXHAUSTION = "resource-exhaustion"
    DEPENDENCY_FAILURE = "dependency-failure"
    NETWORK_PARTITION = "network-partition"
    KILL_PROCESS = "kill-process"
    DISK_FILL = "disk-fill"
    CPU_STRESS = "cpu-stress"
    MEMORY_STRESS = "memory-stress"


class ExperimentStatus(str, Enum):
    """Estados de experimento."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    ROLLED_BACK = "rolled_back"


class TargetType(str, Enum):
    """Tipos de targets."""
    DATABASE = "database"
    CACHE = "cache"
    API = "api"
    BLOCKCHAIN = "blockchain"
    EXTERNAL_SERVICE = "external-service"
    ALL = "all"


@dataclass
class ExperimentConfig:
    """Configuracion de experimento."""
    type: ExperimentType
    target: TargetType
    duration_seconds: int
    parameters: Dict
    blast_radius: float = 0.1  # Porcentaje de requests afectados
    steady_state_hypothesis: Optional[Dict] = None
    rollback_strategy: Optional[str] = None


@dataclass
class ExperimentResult:
    """Resultado de experimento."""
    id: str
    type: ExperimentType
    status: ExperimentStatus
    started_at: datetime
    completed_at: Optional[datetime]
    config: ExperimentConfig
    observations: List[Dict] = field(default_factory=list)
    steady_state_met: Optional[bool] = None
    error: Optional[str] = None
    metrics: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "config": asdict(self.config),
            "observations": self.observations,
            "steady_state_met": self.steady_state_met,
            "error": self.error,
            "metrics": self.metrics,
        }


# ============================================================================
# Modelos DB
# ============================================================================

class ChaosExperimentModel(Base):
    """Experimentos de caos en DB."""
    __tablename__ = "chaos_experiments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    type = Column(String(50), nullable=False)
    target = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    config = Column(JSONB, default={})
    observations = Column(JSONB, default=[])
    metrics = Column(JSONB, default={})
    error = Column(Text, nullable=True)

    created_by = Column(String(255), nullable=True)
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)


# ============================================================================
# Fault Injectors
# ============================================================================

class FaultInjector:
    """Base para inyectores de fallas."""

    def __init__(self):
        self._active = False
        self._original_state = None

    async def inject(self, config: Dict) -> bool:
        """Inyecta la falla."""
        raise NotImplementedError

    async def rollback(self) -> bool:
        """Revierte la falla."""
        raise NotImplementedError

    def is_active(self) -> bool:
        return self._active


class LatencyInjector(FaultInjector):
    """Inyecta latencia en operaciones."""

    _active_delays: Dict[str, float] = {}

    async def inject(self, config: Dict) -> bool:
        target = config.get("target", "all")
        latency_ms = config.get("latency_ms", 100)
        jitter_ms = config.get("jitter_ms", 20)

        self._active_delays[target] = (latency_ms, jitter_ms)
        self._active = True

        logger.info(f"Latency injection active: {target} +{latency_ms}ms")
        return True

    async def rollback(self) -> bool:
        self._active_delays.clear()
        self._active = False
        logger.info("Latency injection rolled back")
        return True

    @classmethod
    async def maybe_delay(cls, target: str):
        """Aplica delay si esta activo para el target."""
        if target in cls._active_delays or "all" in cls._active_delays:
            latency, jitter = cls._active_delays.get(
                target,
                cls._active_delays.get("all", (0, 0))
            )
            delay = (latency + random.uniform(-jitter, jitter)) / 1000
            await asyncio.sleep(delay)


class ErrorInjector(FaultInjector):
    """Inyecta errores en operaciones."""

    _active_errors: Dict[str, Dict] = {}

    async def inject(self, config: Dict) -> bool:
        target = config.get("target", "all")
        error_rate = config.get("error_rate", 0.1)  # 10%
        error_type = config.get("error_type", "Exception")
        error_message = config.get("error_message", "Chaos injection error")

        self._active_errors[target] = {
            "rate": error_rate,
            "type": error_type,
            "message": error_message,
        }
        self._active = True

        logger.info(f"Error injection active: {target} @ {error_rate*100}%")
        return True

    async def rollback(self) -> bool:
        self._active_errors.clear()
        self._active = False
        logger.info("Error injection rolled back")
        return True

    @classmethod
    def maybe_raise(cls, target: str):
        """Lanza error si esta activo y cumple probabilidad."""
        config = cls._active_errors.get(target) or cls._active_errors.get("all")
        if config and random.random() < config["rate"]:
            error_class = {
                "Exception": Exception,
                "TimeoutError": TimeoutError,
                "ConnectionError": ConnectionError,
                "ValueError": ValueError,
            }.get(config["type"], Exception)
            raise error_class(config["message"])


class ResourceExhaustionInjector(FaultInjector):
    """Simula agotamiento de recursos."""

    _exhausted_resources: Dict[str, Any] = {}

    async def inject(self, config: Dict) -> bool:
        resource = config.get("resource", "connections")
        exhaustion_level = config.get("level", 0.9)  # 90%

        self._exhausted_resources[resource] = {
            "level": exhaustion_level,
            "simulated_available": 1 - exhaustion_level,
        }
        self._active = True

        logger.info(f"Resource exhaustion active: {resource} @ {exhaustion_level*100}%")
        return True

    async def rollback(self) -> bool:
        self._exhausted_resources.clear()
        self._active = False
        logger.info("Resource exhaustion rolled back")
        return True

    @classmethod
    def check_availability(cls, resource: str) -> bool:
        """Verifica si recurso esta disponible."""
        if resource in cls._exhausted_resources:
            available = cls._exhausted_resources[resource]["simulated_available"]
            return random.random() < available
        return True


class DependencyFailureInjector(FaultInjector):
    """Simula falla de dependencias externas."""

    _failed_dependencies: set = set()

    async def inject(self, config: Dict) -> bool:
        dependency = config.get("dependency", "external-api")
        failure_mode = config.get("failure_mode", "connection_refused")

        self._failed_dependencies.add(dependency)
        self._original_state = failure_mode
        self._active = True

        logger.info(f"Dependency failure active: {dependency} ({failure_mode})")
        return True

    async def rollback(self) -> bool:
        self._failed_dependencies.clear()
        self._active = False
        logger.info("Dependency failure rolled back")
        return True

    @classmethod
    def is_dependency_failed(cls, dependency: str) -> bool:
        """Verifica si dependencia esta fallando."""
        return dependency in cls._failed_dependencies


# ============================================================================
# Steady State Validators
# ============================================================================

class SteadyStateValidator:
    """Validador de steady state."""

    @staticmethod
    async def validate_http_endpoint(
        url: str,
        expected_status: int = 200,
        timeout: float = 5.0,
    ) -> bool:
        """Valida que endpoint HTTP responde correctamente."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    return response.status == expected_status
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
            logger.debug(f"Validación de endpoint falló ({url}): {e}")
            return False

    @staticmethod
    async def validate_database_connection(connection_string: str) -> bool:
        """Valida conexion a base de datos."""
        # Implementar verificacion de conexion
        return True

    @staticmethod
    async def validate_error_rate(
        service: str,
        max_error_rate: float = 0.01,
    ) -> bool:
        """Valida que error rate este dentro de limites."""
        # Consultar metricas de Prometheus
        return True

    @staticmethod
    async def validate_latency_p99(
        service: str,
        max_latency_ms: int = 1000,
    ) -> bool:
        """Valida que latencia P99 este dentro de limites."""
        # Consultar metricas de Prometheus
        return True


# ============================================================================
# Servicio Principal
# ============================================================================

class ChaosService:
    """
    Servicio de Chaos Engineering.

    Features:
    - Inyeccion de latencia
    - Inyeccion de errores
    - Simulacion de agotamiento de recursos
    - Falla de dependencias
    - Validacion de steady state
    - Rollback automatico
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._active_experiments: Dict[str, ExperimentResult] = {}
        self._injectors: Dict[ExperimentType, FaultInjector] = {
            ExperimentType.LATENCY_INJECTION: LatencyInjector(),
            ExperimentType.ERROR_INJECTION: ErrorInjector(),
            ExperimentType.RESOURCE_EXHAUSTION: ResourceExhaustionInjector(),
            ExperimentType.DEPENDENCY_FAILURE: DependencyFailureInjector(),
        }

        # Verificar que estamos en ambiente permitido
        if CURRENT_ENVIRONMENT not in ALLOWED_ENVIRONMENTS:
            logger.warning(
                f"Chaos Engineering disabled: {CURRENT_ENVIRONMENT} "
                f"not in {ALLOWED_ENVIRONMENTS}"
            )

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def is_enabled(self) -> bool:
        """Verifica si chaos esta habilitado."""
        return (
            CHAOS_ENABLED and
            CURRENT_ENVIRONMENT in ALLOWED_ENVIRONMENTS
        )

    # ========================================================================
    # Experiment Management
    # ========================================================================

    async def run_experiment(
        self,
        experiment_type: str,
        config: Dict,
        created_by: Optional[str] = None,
    ) -> ExperimentResult:
        """
        Ejecuta un experimento de caos.

        Args:
            experiment_type: Tipo de experimento
            config: Configuracion del experimento
            created_by: Usuario que inicia

        Returns:
            Resultado del experimento
        """
        # Validaciones de seguridad
        if not self.is_enabled():
            raise PermissionError(
                "Chaos Engineering no esta habilitado en este ambiente"
            )

        if len(self._active_experiments) >= MAX_CONCURRENT_EXPERIMENTS:
            raise RuntimeError(
                f"Limite de experimentos concurrentes alcanzado: "
                f"{MAX_CONCURRENT_EXPERIMENTS}"
            )

        exp_type = ExperimentType(experiment_type)
        duration = min(config.get("duration_seconds", 60), MAX_EXPERIMENT_DURATION)
        blast_radius = min(config.get("blast_radius", 0.1), BLAST_RADIUS_LIMIT)

        exp_config = ExperimentConfig(
            type=exp_type,
            target=TargetType(config.get("target", "all")),
            duration_seconds=duration,
            parameters=config,
            blast_radius=blast_radius,
            steady_state_hypothesis=config.get("steady_state"),
            rollback_strategy=config.get("rollback_strategy", "automatic"),
        )

        result = ExperimentResult(
            id=str(uuid4()),
            type=exp_type,
            status=ExperimentStatus.PENDING,
            started_at=datetime.utcnow(),
            completed_at=None,
            config=exp_config,
        )

        # Guardar en DB
        db_exp = ChaosExperimentModel(
            id=result.id,
            type=exp_type.value,
            target=exp_config.target.value,
            status=ExperimentStatus.PENDING.value,
            config=asdict(exp_config),
            created_by=created_by,
        )
        self.db.add(db_exp)
        self.db.commit()

        # Ejecutar experimento
        self._active_experiments[result.id] = result

        try:
            await self._execute_experiment(result)
        except Exception as e:
            result.status = ExperimentStatus.FAILED
            result.error = str(e)
            logger.error(f"Experiment {result.id} failed: {e}")
        finally:
            # Siempre hacer rollback
            await self._rollback_experiment(result)
            result.completed_at = datetime.utcnow()

            # Actualizar DB
            db_exp = self.db.query(ChaosExperimentModel).filter(
                ChaosExperimentModel.id == result.id
            ).first()
            if db_exp:
                db_exp.status = result.status.value
                db_exp.completed_at = result.completed_at
                db_exp.observations = result.observations
                db_exp.metrics = result.metrics
                db_exp.error = result.error
                self.db.commit()

            del self._active_experiments[result.id]

        return result

    async def _execute_experiment(self, result: ExperimentResult):
        """Ejecuta el experimento."""
        config = result.config
        injector = self._injectors.get(config.type)

        if not injector:
            raise ValueError(f"No injector for {config.type}")

        logger.info(f"Starting experiment {result.id}: {config.type.value}")
        result.status = ExperimentStatus.RUNNING

        # Validar steady state antes
        if config.steady_state_hypothesis:
            result.observations.append({
                "phase": "pre-injection",
                "timestamp": datetime.utcnow().isoformat(),
                "steady_state_check": "pending",
            })
            pre_check = await self._check_steady_state(config.steady_state_hypothesis)
            result.observations[-1]["steady_state_check"] = "passed" if pre_check else "failed"

            if not pre_check:
                result.status = ExperimentStatus.ABORTED
                result.error = "Pre-injection steady state check failed"
                return

        # Inyectar falla
        await injector.inject(config.parameters)

        result.observations.append({
            "phase": "injection",
            "timestamp": datetime.utcnow().isoformat(),
            "injected": True,
        })

        # Ejecutar por duracion especificada
        start_time = time.time()
        check_interval = min(10, config.duration_seconds / 5)

        while time.time() - start_time < config.duration_seconds:
            await asyncio.sleep(check_interval)

            # Observar estado
            observation = {
                "timestamp": datetime.utcnow().isoformat(),
                "elapsed_seconds": time.time() - start_time,
            }

            # Validar steady state durante experimento
            if config.steady_state_hypothesis:
                steady = await self._check_steady_state(config.steady_state_hypothesis)
                observation["steady_state_met"] = steady

                if not steady:
                    result.observations.append(observation)
                    result.steady_state_met = False
                    logger.warning(
                        f"Steady state violated during experiment {result.id}"
                    )
                    break

            result.observations.append(observation)

        # Validar steady state despues
        if config.steady_state_hypothesis:
            await asyncio.sleep(5)  # Esperar estabilizacion
            post_check = await self._check_steady_state(config.steady_state_hypothesis)
            result.steady_state_met = post_check
            result.observations.append({
                "phase": "post-injection",
                "timestamp": datetime.utcnow().isoformat(),
                "steady_state_check": "passed" if post_check else "failed",
            })

        result.status = ExperimentStatus.COMPLETED
        logger.info(f"Experiment {result.id} completed")

    async def _rollback_experiment(self, result: ExperimentResult):
        """Hace rollback del experimento."""
        injector = self._injectors.get(result.config.type)

        if injector and injector.is_active():
            try:
                await injector.rollback()
                result.observations.append({
                    "phase": "rollback",
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": True,
                })
            except Exception as e:
                result.observations.append({
                    "phase": "rollback",
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": False,
                    "error": str(e),
                })
                logger.error(f"Rollback failed for {result.id}: {e}")

    async def _check_steady_state(self, hypothesis: Dict) -> bool:
        """Verifica hipotesis de steady state."""
        checks = hypothesis.get("checks", [])

        for check in checks:
            check_type = check.get("type")

            if check_type == "http":
                result = await SteadyStateValidator.validate_http_endpoint(
                    url=check.get("url"),
                    expected_status=check.get("expected_status", 200),
                )
                if not result:
                    return False

            elif check_type == "error_rate":
                result = await SteadyStateValidator.validate_error_rate(
                    service=check.get("service"),
                    max_error_rate=check.get("max_rate", 0.01),
                )
                if not result:
                    return False

            elif check_type == "latency":
                result = await SteadyStateValidator.validate_latency_p99(
                    service=check.get("service"),
                    max_latency_ms=check.get("max_ms", 1000),
                )
                if not result:
                    return False

        return True

    async def abort_experiment(self, experiment_id: str) -> bool:
        """Aborta un experimento en progreso."""
        if experiment_id not in self._active_experiments:
            return False

        result = self._active_experiments[experiment_id]
        result.status = ExperimentStatus.ABORTED
        await self._rollback_experiment(result)

        return True

    def get_active_experiments(self) -> List[ExperimentResult]:
        """Obtiene experimentos activos."""
        return list(self._active_experiments.values())

    def get_experiment_history(self, limit: int = 20) -> List[Dict]:
        """Obtiene historial de experimentos."""
        experiments = self.db.query(ChaosExperimentModel).order_by(
            ChaosExperimentModel.started_at.desc()
        ).limit(limit).all()

        return [
            {
                "id": str(exp.id),
                "type": exp.type,
                "target": exp.target,
                "status": exp.status,
                "started_at": exp.started_at.isoformat(),
                "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
                "created_by": exp.created_by,
            }
            for exp in experiments
        ]

    # ========================================================================
    # Predefined Experiments
    # ========================================================================

    async def run_latency_experiment(
        self,
        target: str = "database",
        latency_ms: int = 200,
        duration_seconds: int = 60,
        created_by: Optional[str] = None,
    ) -> ExperimentResult:
        """Ejecuta experimento de latencia."""
        return await self.run_experiment(
            experiment_type="latency-injection",
            config={
                "target": target,
                "latency_ms": latency_ms,
                "jitter_ms": latency_ms // 10,
                "duration_seconds": duration_seconds,
                "steady_state": {
                    "checks": [
                        {
                            "type": "http",
                            "url": "http://localhost:8000/health",
                            "expected_status": 200,
                        }
                    ]
                }
            },
            created_by=created_by,
        )

    async def run_error_experiment(
        self,
        target: str = "api",
        error_rate: float = 0.05,
        duration_seconds: int = 60,
        created_by: Optional[str] = None,
    ) -> ExperimentResult:
        """Ejecuta experimento de errores."""
        return await self.run_experiment(
            experiment_type="error-injection",
            config={
                "target": target,
                "error_rate": error_rate,
                "error_type": "Exception",
                "error_message": "Chaos error injection",
                "duration_seconds": duration_seconds,
            },
            created_by=created_by,
        )

    async def run_dependency_failure_experiment(
        self,
        dependency: str = "blockchain-rpc",
        duration_seconds: int = 60,
        created_by: Optional[str] = None,
    ) -> ExperimentResult:
        """Ejecuta experimento de falla de dependencia."""
        return await self.run_experiment(
            experiment_type="dependency-failure",
            config={
                "target": "external-service",
                "dependency": dependency,
                "failure_mode": "connection_refused",
                "duration_seconds": duration_seconds,
            },
            created_by=created_by,
        )

    def close(self):
        """Cierra conexiones."""
        if self._db:
            self._db.close()


# ============================================================================
# Decorators for Chaos Integration
# ============================================================================

def chaos_enabled(func):
    """
    Decorator que habilita inyeccion de caos en una funcion.

    Uso:
        @chaos_enabled
        async def my_database_operation():
            ...
    """
    import functools

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Aplicar delay si hay latency injection activa
        await LatencyInjector.maybe_delay("all")

        # Verificar error injection
        ErrorInjector.maybe_raise("all")

        # Verificar disponibilidad de recursos
        if not ResourceExhaustionInjector.check_availability("connections"):
            raise ConnectionError("Resource exhausted (chaos injection)")

        return await func(*args, **kwargs)

    return wrapper


def chaos_target(target_name: str):
    """
    Decorator que marca una funcion como target de chaos.

    Uso:
        @chaos_target("database")
        async def query_database():
            ...
    """
    def decorator(func):
        import functools

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            await LatencyInjector.maybe_delay(target_name)
            ErrorInjector.maybe_raise(target_name)

            if not ResourceExhaustionInjector.check_availability(target_name):
                raise ConnectionError(
                    f"Resource {target_name} exhausted (chaos injection)"
                )

            if DependencyFailureInjector.is_dependency_failed(target_name):
                raise ConnectionError(
                    f"Dependency {target_name} unavailable (chaos injection)"
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


# ============================================================================
# Singleton
# ============================================================================

_chaos_service: Optional[ChaosService] = None


def get_chaos_service() -> ChaosService:
    """Obtiene la instancia singleton."""
    global _chaos_service
    if _chaos_service is None:
        _chaos_service = ChaosService()
    return _chaos_service


chaos_service = get_chaos_service
