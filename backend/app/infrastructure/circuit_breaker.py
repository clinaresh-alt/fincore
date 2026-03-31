"""
Circuit Breaker Pattern para servicios externos.
Previene cascadas de fallos y permite modo degradado.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from functools import wraps
from dataclasses import dataclass, field
import threading

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Estados del circuit breaker."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerOpen(Exception):
    """Excepción cuando el circuit breaker está abierto."""

    def __init__(
        self,
        name: str,
        remaining_time: float,
        failure_count: int,
    ):
        self.name = name
        self.remaining_time = remaining_time
        self.failure_count = failure_count
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. "
            f"Retry in {remaining_time:.1f}s. "
            f"Failures: {failure_count}"
        )


@dataclass
class CircuitBreakerStats:
    """Estadísticas del circuit breaker."""
    name: str
    state: CircuitState
    failure_count: int
    success_count: int
    total_calls: int
    last_failure_time: Optional[datetime]
    last_success_time: Optional[datetime]
    last_state_change: datetime
    consecutive_failures: int
    consecutive_successes: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "failure_rate": (
                self.failure_count / self.total_calls * 100
                if self.total_calls > 0
                else 0
            ),
            "last_failure_time": (
                self.last_failure_time.isoformat()
                if self.last_failure_time
                else None
            ),
            "last_success_time": (
                self.last_success_time.isoformat()
                if self.last_success_time
                else None
            ),
            "last_state_change": self.last_state_change.isoformat(),
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
        }


class CircuitBreaker:
    """
    Implementación del patrón Circuit Breaker.

    Estados:
    - CLOSED: Operación normal, las llamadas pasan.
    - OPEN: Circuito abierto por fallos, las llamadas se rechazan.
    - HALF_OPEN: Probando recuperación, permite algunas llamadas.

    Ejemplo de uso:
        cb = CircuitBreaker("external-api", failure_threshold=5)

        @cb
        async def call_external_api():
            ...

        # O manualmente:
        try:
            with cb:
                result = await call_external_api()
        except CircuitBreakerOpen:
            # Usar fallback
            result = get_cached_value()
    """

    # Registry global de circuit breakers
    _registry: Dict[str, "CircuitBreaker"] = {}
    _registry_lock = threading.Lock()

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout: float = 30.0,
        half_open_max_calls: int = 3,
        excluded_exceptions: tuple = (),
        on_open: Optional[Callable[["CircuitBreaker"], None]] = None,
        on_close: Optional[Callable[["CircuitBreaker"], None]] = None,
        on_half_open: Optional[Callable[["CircuitBreaker"], None]] = None,
    ):
        """
        Inicializa el circuit breaker.

        Args:
            name: Nombre identificador
            failure_threshold: Fallos consecutivos para abrir
            success_threshold: Éxitos en half-open para cerrar
            timeout: Segundos antes de intentar half-open
            half_open_max_calls: Máximo de llamadas en half-open
            excluded_exceptions: Excepciones que no cuentan como fallo
            on_open: Callback cuando se abre el circuito
            on_close: Callback cuando se cierra el circuito
            on_half_open: Callback cuando pasa a half-open
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls
        self.excluded_exceptions = excluded_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._total_calls = 0
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None
        self._last_state_change = datetime.utcnow()
        self._opened_at: Optional[float] = None
        self._half_open_calls = 0

        self._on_open = on_open
        self._on_close = on_close
        self._on_half_open = on_half_open

        self._lock = threading.Lock()

        # Registrar en registry global
        with self._registry_lock:
            self._registry[name] = self

        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"failure_threshold={failure_threshold}, timeout={timeout}s"
        )

    @classmethod
    def get(cls, name: str) -> Optional["CircuitBreaker"]:
        """Obtiene un circuit breaker por nombre."""
        with cls._registry_lock:
            return cls._registry.get(name)

    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        """Obtiene estadísticas de todos los circuit breakers."""
        with cls._registry_lock:
            return {
                name: cb.stats.to_dict()
                for name, cb in cls._registry.items()
            }

    @property
    def state(self) -> CircuitState:
        """Estado actual del circuit breaker."""
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        """Estadísticas del circuit breaker."""
        with self._lock:
            return CircuitBreakerStats(
                name=self.name,
                state=self._state,
                failure_count=self._failure_count,
                success_count=self._success_count,
                total_calls=self._total_calls,
                last_failure_time=self._last_failure_time,
                last_success_time=self._last_success_time,
                last_state_change=self._last_state_change,
                consecutive_failures=self._consecutive_failures,
                consecutive_successes=self._consecutive_successes,
            )

    def _check_state_transition(self) -> None:
        """Verifica si debe cambiar de estado."""
        if self._state == CircuitState.OPEN:
            if self._opened_at and (time.time() - self._opened_at >= self.timeout):
                self._transition_to(CircuitState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Realiza transición de estado."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = datetime.utcnow()

        logger.warning(
            f"Circuit breaker '{self.name}' state change: "
            f"{old_state.value} -> {new_state.value}"
        )

        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()
            self._half_open_calls = 0
            if self._on_open:
                try:
                    self._on_open(self)
                except Exception as e:
                    logger.error(f"Error in on_open callback: {e}")

        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._consecutive_successes = 0
            if self._on_half_open:
                try:
                    self._on_half_open(self)
                except Exception as e:
                    logger.error(f"Error in on_half_open callback: {e}")

        elif new_state == CircuitState.CLOSED:
            self._consecutive_failures = 0
            self._opened_at = None
            if self._on_close:
                try:
                    self._on_close(self)
                except Exception as e:
                    logger.error(f"Error in on_close callback: {e}")

    def _record_success(self) -> None:
        """Registra una llamada exitosa."""
        with self._lock:
            self._success_count += 1
            self._total_calls += 1
            self._consecutive_successes += 1
            self._consecutive_failures = 0
            self._last_success_time = datetime.utcnow()

            if self._state == CircuitState.HALF_OPEN:
                if self._consecutive_successes >= self.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

    def _record_failure(self, exception: Exception) -> None:
        """Registra una llamada fallida."""
        # Verificar si la excepción está excluida
        if isinstance(exception, self.excluded_exceptions):
            return

        with self._lock:
            self._failure_count += 1
            self._total_calls += 1
            self._consecutive_failures += 1
            self._consecutive_successes = 0
            self._last_failure_time = datetime.utcnow()

            if self._state == CircuitState.CLOSED:
                if self._consecutive_failures >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

            elif self._state == CircuitState.HALF_OPEN:
                # Un fallo en half-open vuelve a abrir el circuito
                self._transition_to(CircuitState.OPEN)

    def _can_execute(self) -> bool:
        """Verifica si se puede ejecutar una llamada."""
        with self._lock:
            self._check_state_transition()

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                return False

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

            return False

    def _get_remaining_time(self) -> float:
        """Obtiene tiempo restante hasta half-open."""
        if self._opened_at:
            elapsed = time.time() - self._opened_at
            return max(0, self.timeout - elapsed)
        return 0

    def __enter__(self) -> "CircuitBreaker":
        """Context manager para uso síncrono."""
        if not self._can_execute():
            raise CircuitBreakerOpen(
                name=self.name,
                remaining_time=self._get_remaining_time(),
                failure_count=self._consecutive_failures,
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Registra resultado del context manager."""
        if exc_val is None:
            self._record_success()
        else:
            self._record_failure(exc_val)

    async def __aenter__(self) -> "CircuitBreaker":
        """Async context manager."""
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async exit."""
        self.__exit__(exc_type, exc_val, exc_tb)

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorador para funciones."""

        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                async with self:
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                with self:
                    return func(*args, **kwargs)
            return sync_wrapper

    def reset(self) -> None:
        """Resetea el circuit breaker a estado inicial."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            self._opened_at = None
            self._half_open_calls = 0
            self._last_state_change = datetime.utcnow()

        logger.info(f"Circuit breaker '{self.name}' reset to CLOSED")

    def force_open(self) -> None:
        """Fuerza la apertura del circuit breaker."""
        with self._lock:
            self._transition_to(CircuitState.OPEN)
        logger.warning(f"Circuit breaker '{self.name}' forced OPEN")

    def force_close(self) -> None:
        """Fuerza el cierre del circuit breaker."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
        logger.info(f"Circuit breaker '{self.name}' forced CLOSED")


# Circuit breakers pre-configurados para servicios comunes
class ServiceCircuitBreakers:
    """Factory para circuit breakers de servicios."""

    @staticmethod
    def for_database(name: str = "database") -> CircuitBreaker:
        """Circuit breaker para base de datos."""
        return CircuitBreaker(
            name=name,
            failure_threshold=3,
            success_threshold=2,
            timeout=10.0,
            half_open_max_calls=1,
        )

    @staticmethod
    def for_external_api(name: str) -> CircuitBreaker:
        """Circuit breaker para APIs externas."""
        return CircuitBreaker(
            name=name,
            failure_threshold=5,
            success_threshold=3,
            timeout=30.0,
            half_open_max_calls=3,
        )

    @staticmethod
    def for_payment_provider(name: str) -> CircuitBreaker:
        """Circuit breaker para proveedores de pago (más conservador)."""
        return CircuitBreaker(
            name=name,
            failure_threshold=3,
            success_threshold=5,
            timeout=60.0,
            half_open_max_calls=1,
        )

    @staticmethod
    def for_blockchain(name: str = "blockchain") -> CircuitBreaker:
        """Circuit breaker para operaciones blockchain."""
        return CircuitBreaker(
            name=name,
            failure_threshold=5,
            success_threshold=3,
            timeout=120.0,  # RPCs pueden tardar en recuperarse
            half_open_max_calls=2,
        )


# Instancias globales para servicios comunes
stp_circuit_breaker = ServiceCircuitBreakers.for_payment_provider("stp")
bitso_circuit_breaker = ServiceCircuitBreakers.for_external_api("bitso")
blockchain_circuit_breaker = ServiceCircuitBreakers.for_blockchain("blockchain")
chainalysis_circuit_breaker = ServiceCircuitBreakers.for_external_api("chainalysis")
