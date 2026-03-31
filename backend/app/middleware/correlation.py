"""
Middleware para Correlation ID.
Asegura que cada request tenga un ID único para trazabilidad.
"""
import time
import logging
from typing import Callable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.infrastructure.logging import (
    set_correlation_id,
    get_correlation_id,
    get_logger,
)

logger = get_logger(__name__)

# Headers estándar para correlation ID
CORRELATION_ID_HEADERS = [
    "x-correlation-id",
    "x-request-id",
    "request-id",
    "x-trace-id",
]


class CorrelationMiddleware(BaseHTTPMiddleware):
    """
    Middleware que gestiona el Correlation ID para cada request.

    - Extrae el correlation ID de headers entrantes (si existe)
    - Genera uno nuevo si no existe
    - Lo propaga en headers de respuesta
    - Lo hace disponible via contextvars para logging
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Buscar correlation ID en headers
        correlation_id = None
        for header_name in CORRELATION_ID_HEADERS:
            correlation_id = request.headers.get(header_name)
            if correlation_id:
                break

        # Generar uno nuevo si no existe
        if not correlation_id:
            correlation_id = str(uuid4())

        # Establecer en contextvars para logging
        set_correlation_id(correlation_id)

        # Capturar tiempo de inicio
        start_time = time.time()

        # Log de inicio de request
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            client_ip=self._get_client_ip(request),
            user_agent=request.headers.get("user-agent", "")[:100],
        )

        try:
            # Procesar request
            response = await call_next(request)

            # Calcular duración
            duration_ms = (time.time() - start_time) * 1000

            # Log de fin de request
            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            # Añadir correlation ID a headers de respuesta
            response.headers["x-correlation-id"] = correlation_id
            response.headers["x-request-duration-ms"] = str(round(duration_ms, 2))

            return response

        except Exception as e:
            # Log de error
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 2),
                exc_info=True,
            )
            raise

    def _get_client_ip(self, request: Request) -> str:
        """Obtiene la IP real del cliente."""
        # Cloudflare
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip

        # X-Forwarded-For (primer IP)
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()

        # X-Real-IP
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # IP del socket
        if request.client:
            return request.client.host

        return "unknown"
