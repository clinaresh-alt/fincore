"""
Endpoints de Health y Status del Sistema.
"""
import os
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import text
import redis

from app.core.database import get_db
from app.core.config import settings
from app.infrastructure.circuit_breaker import CircuitBreaker
from app.infrastructure.degraded_mode import (
    degraded_mode_manager,
    OperationalMode,
    ServiceStatus,
)
from app.infrastructure.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """
    Health check básico.
    Usado por load balancers y kubernetes probes.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.APP_VERSION,
    }


@router.get("/health/live")
async def liveness_probe():
    """
    Kubernetes liveness probe.
    Verifica que la aplicación está corriendo.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_probe(db: Session = Depends(get_db)):
    """
    Kubernetes readiness probe.
    Verifica que la aplicación puede recibir tráfico.
    """
    checks = {}
    is_ready = True

    # Check database
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        is_ready = False

    # Check Redis (si está configurado)
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            socket_timeout=2,
        )
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"
        # Redis no es crítico para readiness
        logger.warning(f"Redis not available: {e}")

    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "checks": checks},
        )

    return {
        "status": "ready",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health/detailed")
async def detailed_health(
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(None),
):
    """
    Health check detallado con métricas.
    Requiere autenticación de admin.
    """
    admin_key = os.getenv("ADMIN_API_KEY", "")
    if admin_key and x_admin_key != admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    checks: Dict[str, Any] = {}

    # Database
    try:
        result = db.execute(text("""
            SELECT
                numbackends as connections,
                xact_commit as commits,
                xact_rollback as rollbacks,
                blks_read,
                blks_hit,
                tup_returned,
                tup_fetched,
                tup_inserted,
                tup_updated,
                tup_deleted
            FROM pg_stat_database
            WHERE datname = current_database()
        """))
        row = result.fetchone()
        checks["database"] = {
            "status": "ok",
            "connections": row[0] if row else 0,
            "commits": row[1] if row else 0,
            "rollbacks": row[2] if row else 0,
            "cache_hit_ratio": (
                round(row[4] / (row[3] + row[4]) * 100, 2)
                if row and (row[3] + row[4]) > 0
                else 0
            ),
        }
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}

    # Redis
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            socket_timeout=2,
        )
        info = r.info()
        checks["redis"] = {
            "status": "ok",
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "0B"),
            "uptime_seconds": info.get("uptime_in_seconds", 0),
        }
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e)}

    # Circuit Breakers
    cb_stats = CircuitBreaker.get_all_stats()
    open_breakers = [
        name for name, stats in cb_stats.items()
        if stats.get("state") == "open"
    ]
    checks["circuit_breakers"] = {
        "total": len(cb_stats),
        "open": len(open_breakers),
        "open_names": open_breakers,
        "details": cb_stats,
    }

    # Degraded Mode
    dm_status = degraded_mode_manager.get_status()
    checks["operational_mode"] = {
        "mode": dm_status["mode"],
        "is_degraded": dm_status["is_degraded"],
        "disabled_features": dm_status["disabled_features"],
        "healthy_services": dm_status["healthy_services"],
        "total_services": dm_status["total_services"],
    }

    # Overall status
    overall_status = "healthy"
    if checks["database"].get("status") != "ok":
        overall_status = "critical"
    elif open_breakers or dm_status["is_degraded"]:
        overall_status = "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "checks": checks,
    }


@router.get("/system/status")
async def system_status():
    """
    Estado público del sistema.
    No requiere autenticación.
    """
    dm_status = degraded_mode_manager.get_status()

    # Información limitada para endpoint público
    return {
        "status": "operational" if not dm_status["is_degraded"] else "degraded",
        "mode": dm_status["mode"],
        "timestamp": datetime.utcnow().isoformat(),
        "message": (
            "All systems operational"
            if not dm_status["is_degraded"]
            else "Some features may be temporarily unavailable"
        ),
    }


@router.post("/admin/system/mode")
async def set_system_mode(
    mode: str,
    x_admin_key: Optional[str] = Header(None),
):
    """
    Cambia el modo del sistema manualmente.
    Solo para administradores.
    """
    admin_key = os.getenv("ADMIN_API_KEY", "")
    if not admin_key or x_admin_key != admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    try:
        new_mode = OperationalMode(mode)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mode. Valid modes: {[m.value for m in OperationalMode]}",
        )

    degraded_mode_manager.force_mode(new_mode)

    logger.warning(f"System mode manually changed to: {mode}")

    return {
        "message": f"System mode changed to {mode}",
        "mode": mode,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/admin/circuit-breaker/{name}/reset")
async def reset_circuit_breaker(
    name: str,
    x_admin_key: Optional[str] = Header(None),
):
    """
    Resetea un circuit breaker específico.
    """
    admin_key = os.getenv("ADMIN_API_KEY", "")
    if not admin_key or x_admin_key != admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    cb = CircuitBreaker.get(name)
    if not cb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit breaker '{name}' not found",
        )

    cb.reset()

    logger.info(f"Circuit breaker '{name}' reset manually")

    return {
        "message": f"Circuit breaker '{name}' reset",
        "state": cb.state.value,
    }


@router.post("/admin/circuit-breaker/{name}/force-open")
async def force_open_circuit_breaker(
    name: str,
    x_admin_key: Optional[str] = Header(None),
):
    """
    Fuerza la apertura de un circuit breaker.
    Útil para desactivar un servicio problemático.
    """
    admin_key = os.getenv("ADMIN_API_KEY", "")
    if not admin_key or x_admin_key != admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    cb = CircuitBreaker.get(name)
    if not cb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit breaker '{name}' not found",
        )

    cb.force_open()

    logger.warning(f"Circuit breaker '{name}' forced open")

    return {
        "message": f"Circuit breaker '{name}' forced open",
        "state": cb.state.value,
    }
