"""
Servicio de Métricas para Dashboard de FinCore.

Recopila métricas en tiempo real de:
- Remesas (volumen, tasas, tiempos)
- Sistema (CPU, memoria, conexiones)
- Cola de jobs
- Integraciones (STP, Bitso, blockchain)
"""
import os
import time
import asyncio
import logging
import psutil
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.core.database import SessionLocal
from app.schemas.dashboard import (
    RemittanceMetrics,
    FinancialMetrics,
    QueueMetrics,
    SystemMetrics,
    ServiceHealth,
    ServiceStatus,
    IntegrationStatus,
    SystemStatus,
    DashboardSnapshot,
    AlertSummary,
    MetricValue,
    MetricSeries,
    MetricType,
    TimeRange,
)
from app.services.alert_service import get_alert_service

# Redis para cache
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


# ==================== Configuración ====================

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
METRICS_CACHE_TTL = int(os.getenv("METRICS_CACHE_TTL", "10"))  # segundos

# Tiempos de inicio del servidor
SERVER_START_TIME = datetime.utcnow()


# ==================== Servicio de Métricas ====================

class MetricsService:
    """
    Servicio de recopilación y cálculo de métricas.

    Features:
    - Métricas de remesas en tiempo real
    - Estado de integraciones
    - Métricas del sistema
    - Cache con Redis
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._redis: Optional[Any] = None
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}

        self._init_redis()

    def _init_redis(self):
        """Inicializa conexión Redis."""
        if not REDIS_AVAILABLE:
            return

        try:
            self._redis = redis.from_url(REDIS_URL)
            self._redis.ping()
            logger.info("Redis conectado para métricas")
        except Exception as e:
            logger.warning(f"Redis no disponible: {e}")
            self._redis = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def _get_cached(self, key: str) -> Optional[Any]:
        """Obtiene valor de cache."""
        if self._redis:
            try:
                import json
                data = self._redis.get(f"metrics:{key}")
                if data:
                    return json.loads(data)
            except Exception:
                pass

        # Fallback a cache local
        if key in self._cache:
            if time.time() - self._cache_timestamps.get(key, 0) < METRICS_CACHE_TTL:
                return self._cache[key]

        return None

    def _set_cached(self, key: str, value: Any, ttl: int = METRICS_CACHE_TTL):
        """Guarda valor en cache."""
        if self._redis:
            try:
                import json
                self._redis.setex(
                    f"metrics:{key}",
                    ttl,
                    json.dumps(value, default=str)
                )
            except Exception:
                pass

        # Cache local
        self._cache[key] = value
        self._cache_timestamps[key] = time.time()

    # ==================== Métricas de Remesas ====================

    async def get_remittance_metrics(self) -> RemittanceMetrics:
        """Obtiene métricas de remesas."""
        cached = self._get_cached("remittance_metrics")
        if cached:
            return RemittanceMetrics(**cached)

        try:
            from app.models.remittance import Remittance, RemittanceStatus

            now = datetime.utcnow()
            last_hour = now - timedelta(hours=1)
            last_24h = now - timedelta(hours=24)
            last_7d = now - timedelta(days=7)

            # Contar por estado
            status_counts = dict(
                self.db.query(
                    Remittance.status,
                    func.count(Remittance.id)
                ).group_by(Remittance.status).all()
            )

            total = sum(status_counts.values())
            completed = status_counts.get(RemittanceStatus.COMPLETED, 0)
            failed = status_counts.get(RemittanceStatus.FAILED, 0)
            pending = status_counts.get(RemittanceStatus.PENDING_DEPOSIT, 0)
            processing = status_counts.get(RemittanceStatus.PROCESSING, 0) + \
                        status_counts.get(RemittanceStatus.CONVERTING, 0) + \
                        status_counts.get(RemittanceStatus.DISBURSING, 0)

            # Volumen total
            volume_result = self.db.query(
                func.sum(Remittance.amount_crypto_source),
                func.sum(Remittance.amount_fiat_destination),
            ).filter(
                Remittance.status == RemittanceStatus.COMPLETED
            ).first()

            total_usdc = Decimal(str(volume_result[0] or 0))
            total_mxn = Decimal(str(volume_result[1] or 0))

            # Tiempo promedio de procesamiento
            avg_time_result = self.db.query(
                func.avg(
                    func.extract('epoch', Remittance.completed_at - Remittance.created_at)
                )
            ).filter(
                and_(
                    Remittance.status == RemittanceStatus.COMPLETED,
                    Remittance.completed_at.isnot(None)
                )
            ).scalar()

            avg_time = float(avg_time_result or 0)

            # Conteos por período
            last_hour_count = self.db.query(func.count(Remittance.id)).filter(
                Remittance.created_at >= last_hour
            ).scalar() or 0

            last_24h_count = self.db.query(func.count(Remittance.id)).filter(
                Remittance.created_at >= last_24h
            ).scalar() or 0

            last_7d_count = self.db.query(func.count(Remittance.id)).filter(
                Remittance.created_at >= last_7d
            ).scalar() or 0

            # Tasa de éxito
            success_rate = (completed / total * 100) if total > 0 else 0

            metrics = RemittanceMetrics(
                total_count=total,
                completed_count=completed,
                failed_count=failed,
                pending_count=pending,
                processing_count=processing,
                total_volume_usdc=total_usdc,
                total_volume_mxn=total_mxn,
                avg_processing_time_seconds=avg_time,
                success_rate=success_rate,
                last_hour_count=last_hour_count,
                last_24h_count=last_24h_count,
                last_7d_count=last_7d_count,
            )

            self._set_cached("remittance_metrics", metrics.model_dump())
            return metrics

        except Exception as e:
            logger.error(f"Error obteniendo métricas de remesas: {e}")
            return RemittanceMetrics()

    # ==================== Métricas Financieras ====================

    async def get_financial_metrics(self) -> FinancialMetrics:
        """Obtiene métricas financieras."""
        cached = self._get_cached("financial_metrics")
        if cached:
            return FinancialMetrics(**cached)

        try:
            # Obtener balances de servicios
            from app.services.bitso_service import get_bitso_service
            from app.services.exchange_rate_service import get_exchange_rate_service

            bitso = await get_bitso_service()
            exchange = await get_exchange_rate_service()

            # Balance USDC (de Bitso)
            usdc_balance = Decimal("0")
            mxn_balance = Decimal("0")

            try:
                balances = await bitso.get_balances()
                usdc_balance = Decimal(str(balances.get("usdc", {}).get("available", 0)))
                mxn_balance = Decimal(str(balances.get("mxn", {}).get("available", 0)))
            except Exception:
                pass

            # Tasa actual
            current_rate = Decimal("0")
            rate_change = 0.0

            try:
                rate = await exchange.get_rate_usdc_mxn()
                if rate:
                    current_rate = rate.rate
                    # TODO: calcular cambio 24h
            except Exception:
                pass

            # Volumen diario
            from app.models.remittance import Remittance, RemittanceStatus

            yesterday = datetime.utcnow() - timedelta(hours=24)
            daily_volume = self.db.query(
                func.sum(Remittance.amount_crypto_source),
                func.sum(Remittance.amount_fiat_destination),
            ).filter(
                and_(
                    Remittance.status == RemittanceStatus.COMPLETED,
                    Remittance.completed_at >= yesterday
                )
            ).first()

            daily_usdc = Decimal(str(daily_volume[0] or 0))
            daily_mxn = Decimal(str(daily_volume[1] or 0))

            metrics = FinancialMetrics(
                usdc_balance=usdc_balance,
                mxn_balance=mxn_balance,
                usdc_available=usdc_balance,
                mxn_available=mxn_balance,
                daily_volume_usdc=daily_usdc,
                daily_volume_mxn=daily_mxn,
                current_rate_usdc_mxn=current_rate,
                rate_change_24h=rate_change,
            )

            self._set_cached("financial_metrics", metrics.model_dump())
            return metrics

        except Exception as e:
            logger.error(f"Error obteniendo métricas financieras: {e}")
            return FinancialMetrics()

    # ==================== Métricas de Cola ====================

    async def get_queue_metrics(self) -> QueueMetrics:
        """Obtiene métricas de la cola de jobs."""
        cached = self._get_cached("queue_metrics")
        if cached:
            return QueueMetrics(**cached)

        try:
            from app.services.job_queue_service import get_job_queue_service

            queue = await get_job_queue_service()
            stats = await queue.get_stats()

            metrics = QueueMetrics(
                pending_jobs=stats.pending_count,
                processing_jobs=stats.processing_count,
                completed_jobs=stats.completed_count,
                failed_jobs=stats.failed_count,
                dead_letter_jobs=stats.dead_count,
                avg_wait_time_seconds=0,  # TODO: calcular
                avg_processing_time_seconds=stats.avg_processing_time_ms / 1000,
                jobs_per_minute=0,  # TODO: calcular
                error_rate=stats.error_rate,
                active_workers=len(await queue.get_active_workers()),
                jobs_by_type=stats.counts_by_type,
            )

            self._set_cached("queue_metrics", metrics.model_dump())
            return metrics

        except Exception as e:
            logger.error(f"Error obteniendo métricas de cola: {e}")
            return QueueMetrics()

    # ==================== Métricas del Sistema ====================

    async def get_system_metrics(self) -> SystemMetrics:
        """Obtiene métricas del sistema."""
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            uptime = (datetime.utcnow() - SERVER_START_TIME).total_seconds()

            return SystemMetrics(
                cpu_usage=cpu,
                memory_usage=memory.percent,
                disk_usage=disk.percent,
                active_connections=len(psutil.net_connections()),
                requests_per_second=0,  # TODO: de Prometheus
                avg_response_time_ms=0,  # TODO: de Prometheus
                error_rate=0,  # TODO: de Prometheus
                uptime_seconds=int(uptime),
            )

        except Exception as e:
            logger.error(f"Error obteniendo métricas del sistema: {e}")
            return SystemMetrics()

    # ==================== Estado de Servicios ====================

    async def check_service_health(self, service_name: str) -> ServiceHealth:
        """Verifica salud de un servicio."""
        start_time = time.time()

        try:
            if service_name == "database":
                return await self._check_database()
            elif service_name == "redis":
                return await self._check_redis()
            elif service_name == "stp":
                return await self._check_stp()
            elif service_name == "bitso":
                return await self._check_bitso()
            elif service_name == "blockchain":
                return await self._check_blockchain()
            else:
                return ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.UNKNOWN,
                )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ServiceHealth(
                name=service_name,
                status=ServiceStatus.DOWN,
                latency_ms=latency,
                error_message=str(e),
            )

    async def _check_database(self) -> ServiceHealth:
        """Verifica conexión a base de datos."""
        start = time.time()
        try:
            self.db.execute("SELECT 1")
            latency = (time.time() - start) * 1000
            return ServiceHealth(
                name="database",
                status=ServiceStatus.HEALTHY,
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ServiceHealth(
                name="database",
                status=ServiceStatus.DOWN,
                latency_ms=latency,
                error_message=str(e),
            )

    async def _check_redis(self) -> ServiceHealth:
        """Verifica conexión a Redis."""
        start = time.time()
        try:
            if self._redis:
                self._redis.ping()
                latency = (time.time() - start) * 1000
                return ServiceHealth(
                    name="redis",
                    status=ServiceStatus.HEALTHY,
                    latency_ms=latency,
                )
            else:
                return ServiceHealth(
                    name="redis",
                    status=ServiceStatus.DOWN,
                    error_message="Redis no configurado",
                )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ServiceHealth(
                name="redis",
                status=ServiceStatus.DOWN,
                latency_ms=latency,
                error_message=str(e),
            )

    async def _check_stp(self) -> ServiceHealth:
        """Verifica conexión a STP."""
        start = time.time()
        try:
            from app.services.stp_service import get_stp_service

            stp = get_stp_service()
            # Hacer ping o verificar estado
            latency = (time.time() - start) * 1000

            return ServiceHealth(
                name="stp",
                status=ServiceStatus.HEALTHY,
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ServiceHealth(
                name="stp",
                status=ServiceStatus.DOWN,
                latency_ms=latency,
                error_message=str(e),
            )

    async def _check_bitso(self) -> ServiceHealth:
        """Verifica conexión a Bitso."""
        start = time.time()
        try:
            from app.services.bitso_service import get_bitso_service

            bitso = await get_bitso_service()
            await bitso.get_ticker("usdc_mxn")
            latency = (time.time() - start) * 1000

            return ServiceHealth(
                name="bitso",
                status=ServiceStatus.HEALTHY,
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ServiceHealth(
                name="bitso",
                status=ServiceStatus.DOWN,
                latency_ms=latency,
                error_message=str(e),
            )

    async def _check_blockchain(self) -> ServiceHealth:
        """Verifica conexión a blockchain."""
        start = time.time()
        try:
            # TODO: verificar conexión al nodo
            latency = (time.time() - start) * 1000

            return ServiceHealth(
                name="blockchain",
                status=ServiceStatus.HEALTHY,
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ServiceHealth(
                name="blockchain",
                status=ServiceStatus.DOWN,
                latency_ms=latency,
                error_message=str(e),
            )

    async def get_integration_status(self) -> IntegrationStatus:
        """Obtiene estado de todas las integraciones."""
        services = ["database", "redis", "stp", "bitso", "blockchain"]
        health_checks = await asyncio.gather(
            *[self.check_service_health(s) for s in services]
        )

        health_map = {h.name: h for h in health_checks}

        return IntegrationStatus(
            database=health_map.get("database", ServiceHealth(name="database", status=ServiceStatus.UNKNOWN)),
            redis=health_map.get("redis", ServiceHealth(name="redis", status=ServiceStatus.UNKNOWN)),
            stp=health_map.get("stp", ServiceHealth(name="stp", status=ServiceStatus.UNKNOWN)),
            bitso=health_map.get("bitso", ServiceHealth(name="bitso", status=ServiceStatus.UNKNOWN)),
            blockchain=health_map.get("blockchain", ServiceHealth(name="blockchain", status=ServiceStatus.UNKNOWN)),
        )

    async def get_system_status(self) -> SystemStatus:
        """Obtiene estado general del sistema."""
        integrations = await self.get_integration_status()

        # Determinar estado general
        statuses = [
            integrations.database.status,
            integrations.redis.status,
            integrations.stp.status,
            integrations.bitso.status,
        ]

        if any(s == ServiceStatus.DOWN for s in statuses):
            overall = ServiceStatus.DEGRADED
        elif all(s == ServiceStatus.HEALTHY for s in statuses):
            overall = ServiceStatus.HEALTHY
        else:
            overall = ServiceStatus.DEGRADED

        # Contar alertas activas
        alert_service = get_alert_service()
        active_alerts = len(alert_service.get_active_alerts())

        return SystemStatus(
            overall_status=overall,
            services=integrations,
            active_alerts=active_alerts,
        )

    # ==================== Dashboard Snapshot ====================

    async def get_dashboard_snapshot(self) -> DashboardSnapshot:
        """Obtiene snapshot completo del dashboard."""
        # Recopilar todas las métricas en paralelo
        results = await asyncio.gather(
            self.get_remittance_metrics(),
            self.get_financial_metrics(),
            self.get_queue_metrics(),
            self.get_system_metrics(),
            self.get_system_status(),
            return_exceptions=True,
        )

        remittance_metrics = results[0] if not isinstance(results[0], Exception) else RemittanceMetrics()
        financial_metrics = results[1] if not isinstance(results[1], Exception) else FinancialMetrics()
        queue_metrics = results[2] if not isinstance(results[2], Exception) else QueueMetrics()
        system_metrics = results[3] if not isinstance(results[3], Exception) else SystemMetrics()
        system_status = results[4] if not isinstance(results[4], Exception) else SystemStatus(
            overall_status=ServiceStatus.UNKNOWN,
            services=IntegrationStatus(
                database=ServiceHealth(name="database", status=ServiceStatus.UNKNOWN),
                redis=ServiceHealth(name="redis", status=ServiceStatus.UNKNOWN),
                stp=ServiceHealth(name="stp", status=ServiceStatus.UNKNOWN),
                bitso=ServiceHealth(name="bitso", status=ServiceStatus.UNKNOWN),
                blockchain=ServiceHealth(name="blockchain", status=ServiceStatus.UNKNOWN),
            ),
        )

        # Obtener resumen de alertas
        alert_service = get_alert_service()
        alert_summary = alert_service.get_alert_summary()

        # Obtener actividad reciente
        recent_remittances = await self._get_recent_remittances()
        recent_events = await self._get_recent_events()

        return DashboardSnapshot(
            remittances=remittance_metrics,
            financial=financial_metrics,
            queue=queue_metrics,
            system=system_metrics,
            status=system_status,
            alerts=alert_summary,
            recent_remittances=recent_remittances,
            recent_events=recent_events,
        )

    async def _get_recent_remittances(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtiene remesas recientes."""
        try:
            from app.models.remittance import Remittance

            remittances = self.db.query(Remittance).order_by(
                Remittance.created_at.desc()
            ).limit(limit).all()

            return [
                {
                    "id": str(r.id),
                    "reference_code": r.reference_code,
                    "status": r.status.value if hasattr(r.status, 'value') else str(r.status),
                    "amount_source": float(r.amount_crypto_source),
                    "amount_destination": float(r.amount_fiat_destination),
                    "created_at": r.created_at.isoformat(),
                }
                for r in remittances
            ]
        except Exception as e:
            logger.error(f"Error obteniendo remesas recientes: {e}")
            return []

    async def _get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Obtiene eventos recientes del sistema."""
        # TODO: Implementar con tabla de eventos
        return []

    def close(self):
        """Cierra conexiones."""
        if self._db:
            self._db.close()


# ==================== Singleton ====================

_metrics_service: Optional[MetricsService] = None


def get_metrics_service() -> MetricsService:
    """Obtiene la instancia singleton del servicio."""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService()
    return _metrics_service


async def get_metrics_service_async() -> MetricsService:
    """Obtiene el servicio de métricas (async)."""
    return get_metrics_service()
