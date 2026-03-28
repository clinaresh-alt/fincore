"""
FinCore - Sistema Financiero de Alto Nivel
Aplicacion principal FastAPI con seguridad reforzada.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import logging
import os
import time

from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1.router import api_router

# Configurar logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fincore")


# ==================== Rate Limiting Configuration ====================

def get_real_client_ip(request: Request) -> str:
    """
    Obtiene la IP real del cliente considerando proxies.
    Prioridad: X-Forwarded-For > X-Real-IP > client.host
    """
    # Verificar X-Forwarded-For (puede contener múltiples IPs separadas por coma)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Tomar la primera IP (la del cliente original)
        return forwarded_for.split(",")[0].strip()

    # Verificar X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fallback a la IP directa
    return get_remote_address(request)


# Configurar limiter con Redis si está disponible, sino memoria
redis_url = os.getenv("REDIS_URL")
if redis_url and not settings.DEBUG:
    # En producción usar Redis para rate limiting distribuido
    limiter = Limiter(
        key_func=get_real_client_ip,
        storage_uri=redis_url,
        strategy="fixed-window",  # o "moving-window" para más precisión
    )
    logger.info("Rate limiting configurado con Redis")
else:
    # En desarrollo usar memoria
    limiter = Limiter(key_func=get_real_client_ip)
    logger.info("Rate limiting configurado en memoria (desarrollo)")


# ==================== CORS Configuration ====================

def get_cors_origins():
    """
    Obtiene los orígenes CORS permitidos.
    En producción, debe ser una lista específica de dominios.
    """
    if settings.DEBUG:
        # En desarrollo, permitir localhost
        return [
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
        ]

    # En producción, usar la configuración explícita
    # Validar que no haya wildcards
    origins = settings.CORS_ORIGINS
    for origin in origins:
        if "*" in origin:
            logger.warning(
                f"⚠️ CORS: Wildcard detectado en origen '{origin}'. "
                "Esto es inseguro en producción."
            )
    return origins


# Métodos HTTP permitidos (restrictivo)
ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]

# Headers permitidos (solo los necesarios)
ALLOWED_HEADERS = [
    "Authorization",
    "Content-Type",
    "Accept",
    "Origin",
    "X-Requested-With",
    "X-CSRF-Token",
]


# ==================== Application Lifecycle ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager de la aplicacion.
    Ejecuta setup al iniciar y cleanup al cerrar.
    """
    # Startup
    logger.info("Iniciando FinCore...")

    # Crear tablas si no existen (en desarrollo)
    if settings.DEBUG:
        try:
            logger.info("Verificando tablas de base de datos...")
            Base.metadata.create_all(bind=engine)
        except Exception as e:
            logger.warning(f"No se pudieron crear tablas automaticamente: {e}")
            logger.info("Las tablas probablemente ya existen. Continuando...")

    # Iniciar scheduler de jobs (reconciliacion, reembolsos, etc.)
    try:
        from app.core.scheduler import start_scheduler
        start_scheduler()
        logger.info("Scheduler de jobs iniciado")
    except Exception as e:
        logger.warning(f"No se pudo iniciar el scheduler: {e}")

    # Log de configuración de seguridad
    logger.info(f"Rate limiting: {'Redis' if redis_url else 'Memoria'}")
    logger.info(f"CORS origins: {len(get_cors_origins())} dominios configurados")
    logger.info(f"Token expiration: {settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutos")

    logger.info(f"FinCore {settings.APP_VERSION} iniciado correctamente")

    yield

    # Shutdown
    logger.info("Cerrando FinCore...")

    # Detener scheduler
    try:
        from app.core.scheduler import shutdown_scheduler
        shutdown_scheduler()
        logger.info("Scheduler detenido")
    except Exception as e:
        logger.warning(f"Error deteniendo scheduler: {e}")


# ==================== Create Application ====================

app = FastAPI(
    title=settings.APP_NAME,
    description="""
    ## Sistema Core Financiero Next-Gen

    Plataforma integral para gestion de inversiones con:

    - **Autenticacion MFA** (Google Authenticator)
    - **Evaluacion de Proyectos** (VAN, TIR, Payback)
    - **Analisis de Riesgo** (Credit Scoring 0-1000)
    - **Portal del Inversionista** (KPIs en tiempo real)
    - **Vault Seguro** (Documentos cifrados AES-256)

    ### Seguridad
    - Cifrado AES-256 para datos sensibles
    - JWT con expiracion corta (30 min)
    - RBAC (Control de acceso basado en roles)
    - Rate limiting por IP
    - Audit Trail inmutable
    """,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# ==================== Rate Limiting Middleware ====================

# Agregar estado del limiter a la app
app.state.limiter = limiter

# Agregar middleware de rate limiting
app.add_middleware(SlowAPIMiddleware)

# Handler personalizado para rate limit exceeded
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handler personalizado para cuando se excede el rate limit."""
    client_ip = get_real_client_ip(request)
    logger.warning(f"Rate limit excedido para IP {client_ip}: {request.url.path}")

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Demasiadas solicitudes. Por favor espere antes de intentar de nuevo.",
            "retry_after": exc.detail,
        },
        headers={"Retry-After": str(exc.detail)},
    )


# ==================== CORS Middleware ====================

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=ALLOWED_METHODS,
    allow_headers=ALLOWED_HEADERS,
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    max_age=600,  # Cache preflight por 10 minutos
)


# ==================== Security Headers Middleware ====================

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Agrega headers de seguridad a todas las respuestas."""
    response: Response = await call_next(request)

    # Headers de seguridad
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Content Security Policy (solo en producción)
    if not settings.DEBUG:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self' https://api.chainalysis.com https://polygon-rpc.com; "
            "frame-ancestors 'none';"
        )
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

    return response


# ==================== Request Metrics Middleware ====================

# Almacén en memoria para métricas (para Redis usar settings.REDIS_URL)
_request_metrics = {
    "total_requests": 0,
    "total_errors": 0,
    "response_times": [],
    "last_reset": time.time(),
}


@app.middleware("http")
async def collect_request_metrics(request: Request, call_next):
    """Recolecta métricas de requests para monitoreo."""
    start_time = time.time()

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        status_code = 500
        raise

    # Calcular tiempo de respuesta
    response_time_ms = (time.time() - start_time) * 1000

    # Actualizar métricas (thread-safe para asyncio)
    _request_metrics["total_requests"] += 1
    if status_code >= 400:
        _request_metrics["total_errors"] += 1

    # Mantener últimos 1000 tiempos de respuesta
    _request_metrics["response_times"].append(response_time_ms)
    if len(_request_metrics["response_times"]) > 1000:
        _request_metrics["response_times"] = _request_metrics["response_times"][-1000:]

    # Resetear cada minuto para calcular requests/segundo
    elapsed = time.time() - _request_metrics["last_reset"]
    if elapsed > 60:
        _request_metrics["requests_per_second"] = _request_metrics["total_requests"] / elapsed
        _request_metrics["total_requests"] = 0
        _request_metrics["total_errors"] = 0
        _request_metrics["last_reset"] = time.time()

    return response


def get_request_metrics() -> dict:
    """Obtiene las métricas de requests recolectadas."""
    elapsed = time.time() - _request_metrics["last_reset"]
    rps = _request_metrics["total_requests"] / elapsed if elapsed > 0 else 0

    avg_response_time = 0
    if _request_metrics["response_times"]:
        avg_response_time = sum(_request_metrics["response_times"]) / len(_request_metrics["response_times"])

    total = _request_metrics["total_requests"]
    error_rate = _request_metrics["total_errors"] / total if total > 0 else 0

    return {
        "requests_per_second": rps,
        "avg_response_time_ms": avg_response_time,
        "error_rate": error_rate,
    }


# ==================== Trusted Host Middleware ====================

if not settings.DEBUG:
    # En producción, restringir hosts permitidos
    allowed_hosts = os.getenv("ALLOWED_HOSTS", "*.fincore.com,localhost").split(",")
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[h.strip() for h in allowed_hosts]
    )


# ==================== Health Check ====================

@app.get("/health", tags=["Sistema"])
@limiter.limit("60/minute")  # Health checks pueden ser más frecuentes
async def health_check(request: Request):
    """Verifica que el sistema este funcionando."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": "development" if settings.DEBUG else "production"
    }


# ==================== Rate Limited Health Check ====================

@app.get("/api/v1/ping", tags=["Sistema"])
@limiter.limit("10/minute")
async def ping(request: Request):
    """Endpoint de prueba con rate limiting estricto."""
    return {"pong": True}


# ==================== Include API Router ====================

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# ==================== Entry Point ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
