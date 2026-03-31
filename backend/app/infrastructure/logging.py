"""
Sistema de Logging Estructurado JSON con Correlation ID.
Diseñado para producción con soporte para ELK/Datadog/CloudWatch.
"""
import logging
import json
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Optional, Dict
from contextvars import ContextVar
from uuid import uuid4
import os

# Context variable para correlation ID (thread-safe)
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Establece el correlation ID para la request actual."""
    cid = correlation_id or str(uuid4())
    correlation_id_var.set(cid)
    return cid


def get_correlation_id() -> str:
    """Obtiene el correlation ID de la request actual."""
    return correlation_id_var.get() or str(uuid4())


class JSONFormatter(logging.Formatter):
    """
    Formatter que produce logs en formato JSON estructurado.
    Compatible con ELK Stack, Datadog, CloudWatch Logs Insights.
    """

    def __init__(
        self,
        service_name: str = "fincore",
        environment: str = "development",
        include_extra: bool = True,
    ):
        super().__init__()
        self.service_name = service_name
        self.environment = environment
        self.include_extra = include_extra
        self.hostname = os.getenv("HOSTNAME", os.getenv("POD_NAME", "unknown"))
        self.version = os.getenv("APP_VERSION", "1.0.0")

    def format(self, record: logging.LogRecord) -> str:
        """Formatea el log record como JSON."""
        # Campos base obligatorios
        log_data: Dict[str, Any] = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": {
                "name": self.service_name,
                "version": self.version,
                "environment": self.environment,
            },
            "host": {
                "name": self.hostname,
            },
            "source": {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            },
        }

        # Correlation ID
        correlation_id = correlation_id_var.get()
        if correlation_id:
            log_data["trace"] = {
                "id": correlation_id,
                "correlation_id": correlation_id,
            }

        # Process/Thread info
        log_data["process"] = {
            "pid": record.process,
            "name": record.processName,
            "thread": {
                "id": record.thread,
                "name": record.threadName,
            },
        }

        # Exception info
        if record.exc_info:
            log_data["error"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "stack_trace": self.formatException(record.exc_info),
            }

        # Campos extra del log record
        if self.include_extra:
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in {
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "stack_info",
                    "exc_info",
                    "exc_text",
                    "thread",
                    "threadName",
                    "message",
                    "taskName",
                }:
                    try:
                        # Intentar serializar a JSON
                        json.dumps(value)
                        extra_fields[key] = value
                    except (TypeError, ValueError):
                        extra_fields[key] = str(value)

            if extra_fields:
                log_data["extra"] = extra_fields

        return json.dumps(log_data, default=str, ensure_ascii=False)


class StructuredLogger:
    """
    Logger estructurado con soporte para contexto adicional.
    Facilita el logging con campos extra.
    """

    def __init__(self, name: str, default_context: Optional[Dict[str, Any]] = None):
        self._logger = logging.getLogger(name)
        self._default_context = default_context or {}

    def _log(
        self,
        level: int,
        message: str,
        exc_info: bool = False,
        **kwargs: Any,
    ) -> None:
        """Log con contexto adicional."""
        extra = {**self._default_context, **kwargs}
        self._logger.log(level, message, exc_info=exc_info, extra=extra)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, exc_info=exc_info, **kwargs)

    def critical(self, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, message, exc_info=exc_info, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, exc_info=True, **kwargs)

    def with_context(self, **context: Any) -> "StructuredLogger":
        """Retorna un nuevo logger con contexto adicional."""
        new_context = {**self._default_context, **context}
        return StructuredLogger(self._logger.name, new_context)


def setup_logging(
    service_name: str = "fincore",
    environment: str = "development",
    log_level: str = "INFO",
    json_output: bool = True,
) -> None:
    """
    Configura el sistema de logging para la aplicación.

    Args:
        service_name: Nombre del servicio para identificación
        environment: Ambiente (development, staging, production)
        log_level: Nivel de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Si True, usa formato JSON. Si False, formato legible.
    """
    # Obtener nivel de log
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Limpiar handlers existentes
    root_logger.handlers.clear()

    # Crear handler para stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if json_output:
        # Formato JSON para producción
        formatter = JSONFormatter(
            service_name=service_name,
            environment=environment,
        )
    else:
        # Formato legible para desarrollo
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Silenciar loggers ruidosos
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(
    name: str,
    default_context: Optional[Dict[str, Any]] = None,
) -> StructuredLogger:
    """
    Obtiene un logger estructurado.

    Args:
        name: Nombre del logger (generalmente __name__)
        default_context: Contexto por defecto para todos los logs

    Returns:
        StructuredLogger con el contexto configurado
    """
    return StructuredLogger(name, default_context)


# Ejemplo de uso y configuración
class LogContext:
    """Context manager para añadir contexto temporal a los logs."""

    def __init__(self, **context: Any):
        self.context = context
        self.old_correlation_id: Optional[str] = None

    def __enter__(self) -> str:
        # Si hay un correlation_id en el contexto, establecerlo
        if "correlation_id" in self.context:
            self.old_correlation_id = correlation_id_var.get()
            correlation_id_var.set(self.context["correlation_id"])
        return get_correlation_id()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.old_correlation_id is not None:
            correlation_id_var.set(self.old_correlation_id)


# Configuración por defecto al importar
_environment = os.getenv("ENVIRONMENT", "development")
_log_level = os.getenv("LOG_LEVEL", "INFO")
_json_output = os.getenv("LOG_FORMAT", "json").lower() == "json"

setup_logging(
    service_name="fincore",
    environment=_environment,
    log_level=_log_level,
    json_output=_json_output,
)
