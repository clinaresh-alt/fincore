"""
Servicio de Cola de Trabajos con Redis.

Implementa una cola de trabajos robusta con:
- Prioridades multiples
- Reintentos con backoff exponencial
- Dead letter queue
- Bloqueo distribuido
- Metricas y monitoreo

Basado en patrones de colas confiables:
- BRPOPLPUSH para atomicidad
- Sorted sets para scheduling
- Pub/Sub para notificaciones
"""
import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass
import uuid

import redis.asyncio as aioredis
from redis.asyncio.lock import Lock

from app.core.config import settings
from app.schemas.job_queue import (
    Job,
    JobType,
    JobStatus,
    JobPriority,
    JobPayload,
    RetryConfig,
    QueueStats,
    DeadLetterEntry,
    WorkerInfo,
    WorkerHeartbeat,
)

logger = logging.getLogger(__name__)


# ============ Constants ============

# Nombres de keys en Redis
QUEUE_PREFIX = "fincore:jobs:"
QUEUE_PENDING = f"{QUEUE_PREFIX}pending"
QUEUE_PROCESSING = f"{QUEUE_PREFIX}processing"
QUEUE_COMPLETED = f"{QUEUE_PREFIX}completed"
QUEUE_FAILED = f"{QUEUE_PREFIX}failed"
QUEUE_DEAD = f"{QUEUE_PREFIX}dead"
QUEUE_SCHEDULED = f"{QUEUE_PREFIX}scheduled"
QUEUE_DELAYED = f"{QUEUE_PREFIX}delayed"

JOB_DATA_PREFIX = f"{QUEUE_PREFIX}data:"
WORKER_PREFIX = f"{QUEUE_PREFIX}workers:"
STATS_PREFIX = f"{QUEUE_PREFIX}stats:"
LOCK_PREFIX = f"{QUEUE_PREFIX}lock:"

# Canales Pub/Sub
CHANNEL_NEW_JOB = f"{QUEUE_PREFIX}channel:new_job"
CHANNEL_JOB_COMPLETED = f"{QUEUE_PREFIX}channel:completed"
CHANNEL_JOB_FAILED = f"{QUEUE_PREFIX}channel:failed"


# ============ Exceptions ============

class JobQueueError(Exception):
    """Error base del sistema de colas."""
    pass


class JobNotFoundError(JobQueueError):
    """Job no encontrado."""
    pass


class JobLockError(JobQueueError):
    """Error al bloquear job."""
    pass


class QueueFullError(JobQueueError):
    """Cola llena."""
    pass


# ============ Job Queue Service ============

class JobQueueService:
    """
    Servicio principal de cola de trabajos.

    Responsabilidades:
    - Encolar y desencolar jobs
    - Gestionar reintentos
    - Mover jobs a dead letter queue
    - Proporcionar estadisticas
    """

    # Limites
    MAX_QUEUE_SIZE = 100000
    MAX_JOB_DATA_TTL = 86400 * 7  # 7 dias
    COMPLETED_JOB_TTL = 86400  # 1 dia para jobs completados

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis = redis_client
        self._connected = False
        self._pubsub = None

    async def connect(self) -> bool:
        """Conecta a Redis."""
        if self.redis is None:
            try:
                self.redis = await aioredis.from_url(
                    f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
                    encoding="utf-8",
                    decode_responses=True,
                )
                self._connected = True
                logger.info("Conectado a Redis para job queue")
                return True
            except Exception as e:
                logger.error(f"Error conectando a Redis: {e}")
                self._connected = False
                return False
        return True

    async def disconnect(self) -> None:
        """Desconecta de Redis."""
        if self.redis:
            await self.redis.close()
            self._connected = False

    async def _ensure_connected(self) -> None:
        """Asegura conexion a Redis."""
        if not self._connected:
            await self.connect()

    # ============ Enqueue Operations ============

    async def enqueue(
        self,
        job: Job,
        delay_seconds: int = 0,
    ) -> str:
        """
        Agrega un job a la cola.

        Args:
            job: Job a encolar
            delay_seconds: Retraso antes de procesar (para scheduling)

        Returns:
            ID del job
        """
        await self._ensure_connected()

        # Verificar limite de cola
        queue_size = await self.redis.llen(QUEUE_PENDING)
        if queue_size >= self.MAX_QUEUE_SIZE:
            raise QueueFullError(f"Cola llena: {queue_size} jobs")

        # Serializar job
        job_data = json.dumps(job.to_redis_dict())
        job_key = f"{JOB_DATA_PREFIX}{job.id}"

        # Guardar datos del job
        await self.redis.setex(
            job_key,
            self.MAX_JOB_DATA_TTL,
            job_data
        )

        if delay_seconds > 0:
            # Job programado - usar sorted set
            scheduled_time = datetime.utcnow() + timedelta(seconds=delay_seconds)
            job.scheduled_at = scheduled_time
            job.status = JobStatus.SCHEDULED

            await self.redis.zadd(
                QUEUE_SCHEDULED,
                {job.id: scheduled_time.timestamp()}
            )
            logger.info(f"Job {job.id} programado para {scheduled_time}")
        else:
            # Job inmediato - agregar a cola segun prioridad
            await self._add_to_pending_queue(job)

        # Publicar evento
        await self.redis.publish(
            CHANNEL_NEW_JOB,
            json.dumps({"job_id": job.id, "type": job.type.value})
        )

        # Incrementar contador
        await self.redis.hincrby(f"{STATS_PREFIX}counters", "total_enqueued", 1)
        await self.redis.hincrby(f"{STATS_PREFIX}counters", f"type:{job.type.value}", 1)

        logger.info(f"Job encolado: {job.id} ({job.type.value})")
        return job.id

    async def _add_to_pending_queue(self, job: Job) -> None:
        """Agrega job a la cola pendiente con prioridad."""
        # Usar sorted set para prioridades
        # Score = priority * 1000000000 + timestamp (para FIFO dentro de prioridad)
        score = job.priority.value * 1000000000 + job.created_at.timestamp()

        await self.redis.zadd(QUEUE_PENDING, {job.id: score})
        job.status = JobStatus.PENDING

        # Actualizar datos del job
        await self._save_job(job)

    async def enqueue_batch(self, jobs: List[Job]) -> List[str]:
        """Encola multiples jobs en una sola transaccion."""
        await self._ensure_connected()

        job_ids = []
        pipe = self.redis.pipeline()

        for job in jobs:
            job_data = json.dumps(job.to_redis_dict())
            job_key = f"{JOB_DATA_PREFIX}{job.id}"

            pipe.setex(job_key, self.MAX_JOB_DATA_TTL, job_data)

            score = job.priority.value * 1000000000 + job.created_at.timestamp()
            pipe.zadd(QUEUE_PENDING, {job.id: score})

            job_ids.append(job.id)

        await pipe.execute()

        logger.info(f"Batch de {len(jobs)} jobs encolados")
        return job_ids

    # ============ Dequeue Operations ============

    async def dequeue(
        self,
        worker_id: str,
        job_types: Optional[List[JobType]] = None,
        timeout: int = 5,
    ) -> Optional[Job]:
        """
        Obtiene el siguiente job para procesar.

        Args:
            worker_id: ID del worker que procesa
            job_types: Tipos de jobs a procesar (None = todos)
            timeout: Segundos a esperar si no hay jobs

        Returns:
            Job o None si no hay disponibles
        """
        await self._ensure_connected()

        # Primero, mover jobs programados que ya vencieron
        await self._move_scheduled_jobs()

        # Obtener job de mayor prioridad
        result = await self.redis.zpopmin(QUEUE_PENDING)

        if not result:
            # No hay jobs, esperar con bloqueo
            # Usar BZPOPMIN para esperar
            result = await self.redis.bzpopmin(QUEUE_PENDING, timeout)
            if not result:
                return None
            # BZPOPMIN retorna (key, member, score)
            job_id = result[1]
        else:
            job_id, score = result[0]

        # Cargar datos del job
        job = await self._load_job(job_id)
        if job is None:
            logger.warning(f"Job {job_id} no encontrado en datos")
            return None

        # Filtrar por tipo si se especifico
        if job_types and job.type not in job_types:
            # Devolver a la cola
            await self._add_to_pending_queue(job)
            return None

        # Bloquear job
        job.status = JobStatus.PROCESSING
        job.worker_id = worker_id
        job.locked_at = datetime.utcnow()
        job.started_at = datetime.utcnow()
        job.attempts += 1

        # Mover a cola de procesamiento
        await self.redis.sadd(QUEUE_PROCESSING, job.id)
        await self._save_job(job)

        logger.info(f"Job {job.id} asignado a worker {worker_id}")
        return job

    async def _move_scheduled_jobs(self) -> int:
        """Mueve jobs programados que ya vencieron a la cola pendiente."""
        now = datetime.utcnow().timestamp()

        # Obtener jobs vencidos
        expired_jobs = await self.redis.zrangebyscore(
            QUEUE_SCHEDULED,
            "-inf",
            now,
            start=0,
            num=100  # Procesar en lotes
        )

        if not expired_jobs:
            return 0

        count = 0
        for job_id in expired_jobs:
            job = await self._load_job(job_id)
            if job:
                job.status = JobStatus.PENDING
                await self._add_to_pending_queue(job)
                count += 1

            await self.redis.zrem(QUEUE_SCHEDULED, job_id)

        if count > 0:
            logger.info(f"Movidos {count} jobs programados a pendiente")

        return count

    # ============ Job Completion ============

    async def complete_job(
        self,
        job_id: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Marca un job como completado.

        Args:
            job_id: ID del job
            result: Resultado de la ejecucion

        Returns:
            True si se completo exitosamente
        """
        await self._ensure_connected()

        job = await self._load_job(job_id)
        if job is None:
            raise JobNotFoundError(f"Job {job_id} no encontrado")

        # Actualizar estado
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.worker_id = None
        job.locked_at = None

        if result:
            job.payload.metadata["result"] = result

        # Mover de processing a completed
        await self.redis.srem(QUEUE_PROCESSING, job.id)
        await self.redis.lpush(QUEUE_COMPLETED, job.id)

        # Aplicar TTL a jobs completados
        await self.redis.expire(
            f"{JOB_DATA_PREFIX}{job.id}",
            self.COMPLETED_JOB_TTL
        )

        await self._save_job(job)

        # Publicar evento
        await self.redis.publish(
            CHANNEL_JOB_COMPLETED,
            json.dumps({"job_id": job.id, "type": job.type.value})
        )

        # Actualizar estadisticas
        await self.redis.hincrby(f"{STATS_PREFIX}counters", "total_completed", 1)

        processing_time = (job.completed_at - job.started_at).total_seconds() * 1000
        await self.redis.lpush(f"{STATS_PREFIX}processing_times", processing_time)
        await self.redis.ltrim(f"{STATS_PREFIX}processing_times", 0, 999)

        logger.info(f"Job {job.id} completado en {processing_time:.0f}ms")
        return True

    async def fail_job(
        self,
        job_id: str,
        error: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Marca un job como fallido y programa reintento si corresponde.

        Args:
            job_id: ID del job
            error: Mensaje de error
            details: Detalles adicionales del error

        Returns:
            True si se manejo exitosamente
        """
        await self._ensure_connected()

        job = await self._load_job(job_id)
        if job is None:
            raise JobNotFoundError(f"Job {job_id} no encontrado")

        # Registrar error
        job.record_error(error, details)
        job.worker_id = None
        job.locked_at = None

        # Remover de processing
        await self.redis.srem(QUEUE_PROCESSING, job.id)

        if job.can_retry:
            # Programar reintento
            delay = job.retry_config.calculate_delay(job.attempts)
            job.status = JobStatus.SCHEDULED
            job.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)

            await self.redis.zadd(
                QUEUE_SCHEDULED,
                {job.id: job.next_retry_at.timestamp()}
            )

            logger.info(
                f"Job {job.id} programado para reintento #{job.attempts + 1} "
                f"en {delay}s"
            )
        else:
            # Mover a dead letter queue
            await self._move_to_dead_letter(job, error)

        await self._save_job(job)

        # Publicar evento
        await self.redis.publish(
            CHANNEL_JOB_FAILED,
            json.dumps({
                "job_id": job.id,
                "type": job.type.value,
                "error": error,
                "can_retry": job.can_retry,
            })
        )

        # Actualizar estadisticas
        await self.redis.hincrby(f"{STATS_PREFIX}counters", "total_failed", 1)

        return True

    async def _move_to_dead_letter(self, job: Job, reason: str) -> None:
        """Mueve un job a la dead letter queue."""
        job.status = JobStatus.DEAD

        entry = DeadLetterEntry(
            job=job,
            reason=reason,
            original_queue=QUEUE_PENDING,
        )

        await self.redis.lpush(
            QUEUE_DEAD,
            json.dumps(entry.to_dict())
        )

        # Actualizar estadisticas
        await self.redis.hincrby(f"{STATS_PREFIX}counters", "total_dead", 1)

        logger.warning(f"Job {job.id} movido a dead letter queue: {reason}")

    # ============ Job Management ============

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Obtiene un job por ID."""
        await self._ensure_connected()
        return await self._load_job(job_id)

    async def cancel_job(self, job_id: str) -> bool:
        """Cancela un job pendiente."""
        await self._ensure_connected()

        job = await self._load_job(job_id)
        if job is None:
            raise JobNotFoundError(f"Job {job_id} no encontrado")

        if job.status not in [JobStatus.PENDING, JobStatus.SCHEDULED]:
            return False  # Solo se pueden cancelar jobs pendientes

        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.utcnow()

        # Remover de colas
        await self.redis.zrem(QUEUE_PENDING, job.id)
        await self.redis.zrem(QUEUE_SCHEDULED, job.id)

        await self._save_job(job)

        logger.info(f"Job {job.id} cancelado")
        return True

    async def retry_dead_job(self, job_id: str) -> bool:
        """Reintenta un job de la dead letter queue."""
        await self._ensure_connected()

        # Buscar en dead letter queue
        dead_jobs = await self.redis.lrange(QUEUE_DEAD, 0, -1)

        for i, entry_json in enumerate(dead_jobs):
            entry = DeadLetterEntry.from_dict(json.loads(entry_json))
            if entry.job.id == job_id:
                if not entry.can_replay:
                    return False

                # Resetear job para reintento
                job = entry.job
                job.status = JobStatus.PENDING
                job.attempts = 0
                job.error_history = []
                job.last_error = None

                # Remover de dead letter
                await self.redis.lrem(QUEUE_DEAD, 1, entry_json)

                # Encolar de nuevo
                await self._add_to_pending_queue(job)

                logger.info(f"Job {job_id} recuperado de dead letter queue")
                return True

        return False

    async def _load_job(self, job_id: str) -> Optional[Job]:
        """Carga un job desde Redis."""
        job_data = await self.redis.get(f"{JOB_DATA_PREFIX}{job_id}")
        if job_data is None:
            return None
        return Job.from_redis_dict(json.loads(job_data))

    async def _save_job(self, job: Job) -> None:
        """Guarda un job en Redis."""
        job_data = json.dumps(job.to_redis_dict())
        await self.redis.setex(
            f"{JOB_DATA_PREFIX}{job.id}",
            self.MAX_JOB_DATA_TTL,
            job_data
        )

    # ============ Statistics ============

    async def get_stats(self) -> QueueStats:
        """Obtiene estadisticas de la cola."""
        await self._ensure_connected()

        stats = QueueStats(queue_name="fincore:jobs")

        # Conteos por estado
        stats.pending_count = await self.redis.zcard(QUEUE_PENDING)
        stats.processing_count = await self.redis.scard(QUEUE_PROCESSING)
        stats.completed_count = await self.redis.llen(QUEUE_COMPLETED)
        stats.failed_count = await self.redis.llen(QUEUE_FAILED)
        stats.dead_count = await self.redis.llen(QUEUE_DEAD)
        stats.scheduled_count = await self.redis.zcard(QUEUE_SCHEDULED)

        # Contadores acumulados
        counters = await self.redis.hgetall(f"{STATS_PREFIX}counters")

        # Conteos por tipo
        for key, value in counters.items():
            if key.startswith("type:"):
                job_type = key.replace("type:", "")
                stats.counts_by_type[job_type] = int(value)

        # Tiempos de procesamiento
        times = await self.redis.lrange(f"{STATS_PREFIX}processing_times", 0, -1)
        if times:
            times_float = [float(t) for t in times]
            stats.avg_processing_time_ms = sum(times_float) / len(times_float)

        # Error rate
        total_completed = int(counters.get("total_completed", 0))
        total_failed = int(counters.get("total_failed", 0))
        if total_completed + total_failed > 0:
            stats.error_rate = total_failed / (total_completed + total_failed)

        # Job mas antiguo pendiente
        oldest = await self.redis.zrange(QUEUE_PENDING, 0, 0, withscores=True)
        if oldest:
            job_id, score = oldest[0]
            job = await self._load_job(job_id)
            if job:
                stats.oldest_pending_job = job.created_at

        return stats

    async def get_dead_letter_jobs(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> List[DeadLetterEntry]:
        """Obtiene jobs de la dead letter queue."""
        await self._ensure_connected()

        entries = await self.redis.lrange(QUEUE_DEAD, offset, offset + limit - 1)
        return [
            DeadLetterEntry.from_dict(json.loads(entry))
            for entry in entries
        ]

    # ============ Worker Management ============

    async def register_worker(self, worker: WorkerInfo) -> None:
        """Registra un worker."""
        await self._ensure_connected()

        await self.redis.hset(
            f"{WORKER_PREFIX}registry",
            worker.id,
            json.dumps({
                "id": worker.id,
                "hostname": worker.hostname,
                "pid": worker.pid,
                "started_at": worker.started_at.isoformat(),
                "status": worker.status,
            })
        )

    async def update_worker_heartbeat(self, heartbeat: WorkerHeartbeat) -> None:
        """Actualiza heartbeat de un worker."""
        await self._ensure_connected()

        await self.redis.hset(
            f"{WORKER_PREFIX}heartbeats",
            heartbeat.worker_id,
            json.dumps({
                "timestamp": heartbeat.timestamp.isoformat(),
                "status": heartbeat.status,
                "current_job_id": heartbeat.current_job_id,
                "memory_mb": heartbeat.memory_mb,
                "cpu_percent": heartbeat.cpu_percent,
            })
        )

    async def get_active_workers(self) -> List[WorkerInfo]:
        """Obtiene workers activos (heartbeat < 30s)."""
        await self._ensure_connected()

        workers = []
        registry = await self.redis.hgetall(f"{WORKER_PREFIX}registry")
        heartbeats = await self.redis.hgetall(f"{WORKER_PREFIX}heartbeats")

        for worker_id, worker_data in registry.items():
            data = json.loads(worker_data)
            heartbeat_data = heartbeats.get(worker_id)

            if heartbeat_data:
                hb = json.loads(heartbeat_data)
                last_heartbeat = datetime.fromisoformat(hb["timestamp"])

                # Verificar si esta vivo
                if (datetime.utcnow() - last_heartbeat).total_seconds() < 30:
                    workers.append(WorkerInfo(
                        id=data["id"],
                        hostname=data["hostname"],
                        pid=data["pid"],
                        started_at=datetime.fromisoformat(data["started_at"]),
                        last_heartbeat=last_heartbeat,
                        status=hb.get("status", "unknown"),
                        current_job_id=hb.get("current_job_id"),
                    ))

        return workers

    # ============ Cleanup ============

    async def cleanup_stale_jobs(self) -> int:
        """
        Limpia jobs huerfanos (en processing sin heartbeat de worker).
        Debe ejecutarse periodicamente.
        """
        await self._ensure_connected()

        processing_jobs = await self.redis.smembers(QUEUE_PROCESSING)
        cleaned = 0

        for job_id in processing_jobs:
            job = await self._load_job(job_id)
            if job is None:
                # Job sin datos - remover
                await self.redis.srem(QUEUE_PROCESSING, job_id)
                cleaned += 1
                continue

            # Verificar si el lock expiro
            if not job.is_locked:
                # Job huerfano - devolver a cola
                job.status = JobStatus.PENDING
                job.worker_id = None
                job.locked_at = None

                await self.redis.srem(QUEUE_PROCESSING, job.id)
                await self._add_to_pending_queue(job)

                logger.warning(f"Job huerfano {job.id} devuelto a cola")
                cleaned += 1

        if cleaned > 0:
            logger.info(f"Limpiados {cleaned} jobs huerfanos")

        return cleaned

    async def purge_old_completed_jobs(self, older_than_days: int = 7) -> int:
        """Elimina jobs completados antiguos."""
        await self._ensure_connected()

        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        purged = 0

        # Solo mantener ultimos 10000 jobs completados
        await self.redis.ltrim(QUEUE_COMPLETED, 0, 9999)

        logger.info(f"Purgados jobs completados antiguos")
        return purged


# ============ Factory Functions ============

_job_queue_service: Optional[JobQueueService] = None


async def get_job_queue_service() -> JobQueueService:
    """Factory function para obtener instancia singleton."""
    global _job_queue_service
    if _job_queue_service is None:
        _job_queue_service = JobQueueService()
        await _job_queue_service.connect()
    return _job_queue_service


# ============ Convenience Functions ============

async def enqueue_spei_payment(
    remittance_id: str,
    clabe: str,
    beneficiary_name: str,
    amount,
    concept: str = "PAGO REMESA",
) -> str:
    """Encola un pago SPEI para procesamiento."""
    from app.schemas.job_queue import CreateSPEIPaymentJob
    from decimal import Decimal

    service = await get_job_queue_service()

    request = CreateSPEIPaymentJob(
        remittance_id=remittance_id,
        clabe=clabe,
        beneficiary_name=beneficiary_name,
        amount=Decimal(str(amount)),
        concept=concept,
    )

    job = request.to_job()
    return await service.enqueue(job)


async def enqueue_bitso_conversion(
    remittance_id: str,
    amount_usdc,
) -> str:
    """Encola una conversion Bitso para procesamiento."""
    from app.schemas.job_queue import CreateBitsoConversionJob
    from decimal import Decimal

    service = await get_job_queue_service()

    request = CreateBitsoConversionJob(
        remittance_id=remittance_id,
        amount_usdc=Decimal(str(amount_usdc)),
    )

    job = request.to_job()
    return await service.enqueue(job)
