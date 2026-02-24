"""
FinCore - Sistema Financiero de Alto Nivel
Aplicacion principal FastAPI.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import logging

from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1.router import api_router

# Configurar logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fincore")


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
        logger.info("Creando tablas de base de datos...")
        Base.metadata.create_all(bind=engine)

    logger.info(f"FinCore {settings.APP_VERSION} iniciado correctamente")

    yield

    # Shutdown
    logger.info("Cerrando FinCore...")


# Crear aplicacion FastAPI
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
    - JWT con expiracion corta (15 min)
    - RBAC (Control de acceso basado en roles)
    - Audit Trail inmutable
    """,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Middleware de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware de hosts confiables (produccion)
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.fincore.com", "localhost"]
    )


# Health check
@app.get("/health", tags=["Sistema"])
async def health_check():
    """Verifica que el sistema este funcionando."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": "development" if settings.DEBUG else "production"
    }


# Incluir router de API v1
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# Punto de entrada para uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
