"""
Middleware para exponer estado de Circuit Breakers.
"""
import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.infrastructure.circuit_breaker import CircuitBreaker
from app.infrastructure.logging import get_logger

logger = get_logger(__name__)


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """
    Middleware que expone el estado de los circuit breakers.

    Proporciona:
    - Endpoint /circuit-breakers/status para monitoreo
    - Headers con estado general
    """

    def __init__(
        self,
        app,
        status_path: str = "/circuit-breakers/status",
        require_auth: bool = True,
        auth_header: str = "x-admin-key",
        admin_key: str = "",
    ):
        """
        Inicializa el middleware.

        Args:
            app: Aplicación ASGI
            status_path: Ruta para el endpoint de estado
            require_auth: Si requiere autenticación
            auth_header: Header de autenticación
            admin_key: Clave de admin para acceso
        """
        super().__init__(app)
        self.status_path = status_path
        self.require_auth = require_auth
        self.auth_header = auth_header
        self.admin_key = admin_key

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Endpoint de estado de circuit breakers
        if request.url.path == self.status_path:
            # Verificar autenticación si es requerida
            if self.require_auth and self.admin_key:
                auth = request.headers.get(self.auth_header)
                if auth != self.admin_key:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Unauthorized"},
                    )

            # Obtener estado de todos los circuit breakers
            stats = CircuitBreaker.get_all_stats()

            # Calcular estado general
            all_closed = all(
                s.get("state") == "closed"
                for s in stats.values()
            )

            return JSONResponse(
                content={
                    "status": "healthy" if all_closed else "degraded",
                    "circuit_breakers": stats,
                    "total": len(stats),
                    "open_count": sum(
                        1 for s in stats.values()
                        if s.get("state") == "open"
                    ),
                    "half_open_count": sum(
                        1 for s in stats.values()
                        if s.get("state") == "half_open"
                    ),
                },
            )

        # Procesar request normalmente
        response = await call_next(request)

        # Añadir header con estado general si hay circuit breakers abiertos
        stats = CircuitBreaker.get_all_stats()
        open_cbs = [
            name for name, s in stats.items()
            if s.get("state") == "open"
        ]

        if open_cbs:
            response.headers["X-Circuit-Breakers-Open"] = ",".join(open_cbs)
            response.headers["X-System-Status"] = "degraded"
        else:
            response.headers["X-System-Status"] = "healthy"

        return response
