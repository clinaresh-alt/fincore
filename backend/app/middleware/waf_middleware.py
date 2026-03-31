"""
Middleware WAF para validación de requests.
"""
import logging
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.infrastructure.waf import CloudflareWAF, WAFConfig
from app.infrastructure.logging import get_logger

logger = get_logger(__name__)


class WAFMiddleware(BaseHTTPMiddleware):
    """
    Middleware que integra validación WAF de Cloudflare.

    Verifica:
    - Que la request venga de Cloudflare
    - Headers de seguridad
    - Rate limiting local (backup)
    - Geo blocking
    """

    def __init__(
        self,
        app,
        waf: Optional[CloudflareWAF] = None,
        exclude_paths: Optional[list] = None,
    ):
        """
        Inicializa el middleware WAF.

        Args:
            app: Aplicación ASGI
            waf: Instancia de CloudflareWAF (opcional)
            exclude_paths: Rutas a excluir de validación
        """
        super().__init__(app)
        self.waf = waf or CloudflareWAF()
        self.exclude_paths = exclude_paths or [
            "/health",
            "/healthz",
            "/ready",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Excluir ciertas rutas
        if any(request.url.path.startswith(p) for p in self.exclude_paths):
            return await call_next(request)

        # Obtener IP del cliente
        remote_ip = request.client.host if request.client else "unknown"

        # Convertir headers a dict
        headers = dict(request.headers)

        # Validar request
        validation = self.waf.validate_request(remote_ip, headers)

        if not validation["allowed"]:
            logger.warning(
                "Request blocked by WAF",
                reason=validation["reason"],
                client_ip=validation["client_ip"] or remote_ip,
                path=request.url.path,
                cf_ray=validation.get("cf_ray"),
            )

            # Determinar código de respuesta según razón
            status_code = 403
            if validation["reason"] == "rate_limit_exceeded":
                status_code = 429

            return JSONResponse(
                status_code=status_code,
                content={
                    "error": "Access denied",
                    "code": validation["reason"],
                },
                headers={
                    "X-Correlation-ID": headers.get("x-correlation-id", ""),
                },
            )

        # Request permitida - continuar
        response = await call_next(request)

        # Añadir headers de seguridad
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Si hay CF-Ray, pasarlo en respuesta
        if validation.get("cf_ray"):
            response.headers["X-CF-Ray"] = validation["cf_ray"]

        return response
