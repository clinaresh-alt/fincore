"""
Tests para el sistema de colas de jobs.

Cubre:
- Enqueue/Dequeue de jobs
- Reintentos con backoff exponencial
- Dead letter queue
- Estadisticas
- Worker management
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from decimal import Decimal
import json
import asyncio

from app.services.job_queue_service import (
    JobQueueService,
    JobQueueError,
    JobNotFoundError,
    JobLockError,
    QueueFullError,
    QUEUE_PENDING,
    QUEUE_PROCESSING,
    QUEUE_DEAD,
)
from app.schemas.job_queue import (
    Job,
    JobType,
    JobStatus,
    JobPriority,
    JobPayload,
    RetryConfig,
    RetryStrategy,
    QueueStats,
    DeadLetterEntry,
    WorkerInfo,
    WorkerHeartbeat,
    CreateSPEIPaymentJob,
    CreateBitsoConversionJob,
)


# ==================== FIXTURES ====================

@pytest.fixture
def mock_redis():
    """Mock de cliente Redis."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.llen = AsyncMock(return_value=0)
    redis.lpush = AsyncMock(return_value=1)
    redis.lrange = AsyncMock(return_value=[])
    redis.lrem = AsyncMock(return_value=1)
    redis.sadd = AsyncMock(return_value=1)
    redis.srem = AsyncMock(return_value=1)
    redis.smembers = AsyncMock(return_value=set())
    redis.scard = AsyncMock(return_value=0)
    redis.zadd = AsyncMock(return_value=1)
    redis.zrem = AsyncMock(return_value=1)
    redis.zcard = AsyncMock(return_value=0)
    redis.zpopmin = AsyncMock(return_value=[])
    redis.bzpopmin = AsyncMock(return_value=None)
    redis.zrangebyscore = AsyncMock(return_value=[])
    redis.zrange = AsyncMock(return_value=[])
    redis.hincrby = AsyncMock(return_value=1)
    redis.hgetall = AsyncMock(return_value={})
    redis.hset = AsyncMock(return_value=1)
    redis.publish = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.pipeline = MagicMock(return_value=AsyncMock())
    return redis


@pytest.fixture
def queue_service(mock_redis):
    """Servicio de cola para tests."""
    service = JobQueueService(redis_client=mock_redis)
    service._connected = True
    return service


@pytest.fixture
def sample_job():
    """Job de ejemplo."""
    return Job(
        type=JobType.SPEI_PAYMENT,
        priority=JobPriority.HIGH,
        remittance_id="rem_123",
        payload=JobPayload(data={
            "clabe": "012180015678912345",
            "beneficiary_name": "JUAN PEREZ",
            "amount": "1500.00",
            "concept": "PAGO REMESA",
        }),
    )


@pytest.fixture
def sample_retry_config():
    """Configuracion de reintentos de ejemplo."""
    return RetryConfig(
        max_retries=5,
        strategy=RetryStrategy.EXPONENTIAL,
        base_delay_seconds=10,
        max_delay_seconds=3600,
        jitter=False,
    )


# ==================== TESTS: RetryConfig ====================

class TestRetryConfig:
    """Tests para configuracion de reintentos."""

    def test_exponential_backoff(self, sample_retry_config):
        """Backoff exponencial debe calcular correctamente."""
        config = sample_retry_config

        assert config.calculate_delay(0) == 10   # 10 * 2^0 = 10
        assert config.calculate_delay(1) == 20   # 10 * 2^1 = 20
        assert config.calculate_delay(2) == 40   # 10 * 2^2 = 40
        assert config.calculate_delay(3) == 80   # 10 * 2^3 = 80
        assert config.calculate_delay(4) == 160  # 10 * 2^4 = 160

    def test_exponential_max_delay(self, sample_retry_config):
        """Delay no debe exceder max_delay_seconds."""
        config = sample_retry_config

        # 10 * 2^10 = 10240 > 3600, debe truncar
        delay = config.calculate_delay(10)
        assert delay == 3600

    def test_linear_backoff(self):
        """Backoff lineal debe incrementar linealmente."""
        config = RetryConfig(
            strategy=RetryStrategy.LINEAR,
            base_delay_seconds=10,
            jitter=False,
        )

        assert config.calculate_delay(0) == 10
        assert config.calculate_delay(1) == 20
        assert config.calculate_delay(2) == 30
        assert config.calculate_delay(3) == 40

    def test_fixed_delay(self):
        """Delay fijo debe ser constante."""
        config = RetryConfig(
            strategy=RetryStrategy.FIXED,
            base_delay_seconds=30,
            jitter=False,
        )

        assert config.calculate_delay(0) == 30
        assert config.calculate_delay(1) == 30
        assert config.calculate_delay(5) == 30

    def test_fibonacci_backoff(self):
        """Backoff fibonacci debe seguir secuencia."""
        config = RetryConfig(
            strategy=RetryStrategy.FIBONACCI,
            base_delay_seconds=5,
            jitter=False,
        )

        # Fibonacci: 1, 1, 2, 3, 5, 8, 13...
        assert config.calculate_delay(0) == 5   # base
        assert config.calculate_delay(1) == 5   # 5 * 1
        assert config.calculate_delay(2) == 10  # 5 * 2
        assert config.calculate_delay(3) == 15  # 5 * 3
        assert config.calculate_delay(4) == 25  # 5 * 5


# ==================== TESTS: Job Model ====================

class TestJobModel:
    """Tests para el modelo Job."""

    def test_job_creation(self, sample_job):
        """Job debe crearse con valores por defecto correctos."""
        assert sample_job.id is not None
        assert sample_job.status == JobStatus.PENDING
        assert sample_job.attempts == 0
        assert sample_job.created_at is not None

    def test_job_can_retry_true(self, sample_job):
        """can_retry debe ser True si hay reintentos disponibles."""
        sample_job.status = JobStatus.FAILED
        sample_job.attempts = 2
        sample_job.retry_config.max_retries = 5

        assert sample_job.can_retry is True

    def test_job_can_retry_false_max_attempts(self, sample_job):
        """can_retry debe ser False si se agotaron reintentos."""
        sample_job.status = JobStatus.FAILED
        sample_job.attempts = 5
        sample_job.retry_config.max_retries = 5

        assert sample_job.can_retry is False

    def test_job_can_retry_false_wrong_status(self, sample_job):
        """can_retry debe ser False si no esta en estado FAILED."""
        sample_job.status = JobStatus.COMPLETED
        sample_job.attempts = 1

        assert sample_job.can_retry is False

    def test_job_is_expired(self, sample_job):
        """is_expired debe detectar jobs expirados."""
        # No expirado (sin expires_at)
        assert sample_job.is_expired is False

        # No expirado
        sample_job.expires_at = datetime.utcnow() + timedelta(hours=1)
        assert sample_job.is_expired is False

        # Expirado
        sample_job.expires_at = datetime.utcnow() - timedelta(hours=1)
        assert sample_job.is_expired is True

    def test_job_is_locked(self, sample_job):
        """is_locked debe verificar bloqueo activo."""
        # No bloqueado
        assert sample_job.is_locked is False

        # Bloqueado
        sample_job.locked_at = datetime.utcnow()
        sample_job.lock_timeout_seconds = 300
        assert sample_job.is_locked is True

        # Lock expirado
        sample_job.locked_at = datetime.utcnow() - timedelta(seconds=400)
        assert sample_job.is_locked is False

    def test_job_serialization(self, sample_job):
        """Job debe serializarse y deserializarse correctamente."""
        data = sample_job.to_redis_dict()
        restored = Job.from_redis_dict(data)

        assert restored.id == sample_job.id
        assert restored.type == sample_job.type
        assert restored.status == sample_job.status
        assert restored.priority == sample_job.priority
        assert restored.payload.data == sample_job.payload.data

    def test_job_record_error(self, sample_job):
        """record_error debe agregar error al historial."""
        sample_job.record_error("Connection timeout", {"host": "api.bitso.com"})

        assert sample_job.last_error == "Connection timeout"
        assert len(sample_job.error_history) == 1
        assert sample_job.error_history[0]["error"] == "Connection timeout"


# ==================== TESTS: Queue Service - Enqueue ====================

class TestQueueServiceEnqueue:
    """Tests para operaciones de enqueue."""

    @pytest.mark.asyncio
    async def test_enqueue_job(self, queue_service, sample_job, mock_redis):
        """Debe encolar job correctamente."""
        job_id = await queue_service.enqueue(sample_job)

        assert job_id == sample_job.id
        mock_redis.setex.assert_called()
        mock_redis.zadd.assert_called()
        mock_redis.publish.assert_called()

    @pytest.mark.asyncio
    async def test_enqueue_with_delay(self, queue_service, sample_job, mock_redis):
        """Debe programar job con delay."""
        job_id = await queue_service.enqueue(sample_job, delay_seconds=60)

        assert job_id == sample_job.id
        # Debe agregar a cola de scheduled, no pending
        mock_redis.zadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_queue_full(self, queue_service, sample_job, mock_redis):
        """Debe rechazar si cola esta llena."""
        mock_redis.llen.return_value = queue_service.MAX_QUEUE_SIZE + 1

        with pytest.raises(QueueFullError):
            await queue_service.enqueue(sample_job)

    @pytest.mark.asyncio
    async def test_enqueue_batch(self, queue_service, mock_redis):
        """Debe encolar multiples jobs en batch."""
        jobs = [
            Job(type=JobType.SPEI_PAYMENT, payload=JobPayload(data={"i": i}))
            for i in range(5)
        ]

        job_ids = await queue_service.enqueue_batch(jobs)

        assert len(job_ids) == 5


# ==================== TESTS: Queue Service - Dequeue ====================

class TestQueueServiceDequeue:
    """Tests para operaciones de dequeue."""

    @pytest.mark.asyncio
    async def test_dequeue_job(self, queue_service, sample_job, mock_redis):
        """Debe desencolar job correctamente."""
        # Simular job en cola
        mock_redis.zpopmin.return_value = [(sample_job.id, 1.0)]
        mock_redis.get.return_value = json.dumps(sample_job.to_redis_dict())

        job = await queue_service.dequeue("worker-1")

        assert job is not None
        assert job.id == sample_job.id
        assert job.status == JobStatus.PROCESSING
        assert job.worker_id == "worker-1"
        assert job.attempts == 1

    @pytest.mark.asyncio
    async def test_dequeue_empty_queue(self, queue_service, mock_redis):
        """Debe retornar None si cola esta vacia."""
        mock_redis.zpopmin.return_value = []
        mock_redis.bzpopmin.return_value = None

        job = await queue_service.dequeue("worker-1", timeout=1)

        assert job is None


# ==================== TESTS: Queue Service - Complete/Fail ====================

class TestQueueServiceCompletion:
    """Tests para completar/fallar jobs."""

    @pytest.mark.asyncio
    async def test_complete_job(self, queue_service, sample_job, mock_redis):
        """Debe marcar job como completado."""
        mock_redis.get.return_value = json.dumps(sample_job.to_redis_dict())

        await queue_service.complete_job(sample_job.id, {"success": True})

        mock_redis.srem.assert_called_with(QUEUE_PROCESSING, sample_job.id)
        mock_redis.lpush.assert_called()
        mock_redis.publish.assert_called()

    @pytest.mark.asyncio
    async def test_complete_job_not_found(self, queue_service, mock_redis):
        """Debe lanzar error si job no existe."""
        mock_redis.get.return_value = None

        with pytest.raises(JobNotFoundError):
            await queue_service.complete_job("nonexistent")

    @pytest.mark.asyncio
    async def test_fail_job_with_retry(self, queue_service, sample_job, mock_redis):
        """Debe programar reintento si hay disponibles."""
        sample_job.attempts = 1
        mock_redis.get.return_value = json.dumps(sample_job.to_redis_dict())

        await queue_service.fail_job(sample_job.id, "Connection error")

        # Debe agregar a scheduled para reintento
        mock_redis.zadd.assert_called()

    @pytest.mark.asyncio
    async def test_fail_job_move_to_dead(self, queue_service, sample_job, mock_redis):
        """Debe mover a dead letter si no hay reintentos."""
        sample_job.attempts = sample_job.retry_config.max_retries
        sample_job.status = JobStatus.FAILED
        mock_redis.get.return_value = json.dumps(sample_job.to_redis_dict())

        await queue_service.fail_job(sample_job.id, "Max retries exceeded")

        # Debe agregar a dead letter queue
        dead_calls = [
            call for call in mock_redis.lpush.call_args_list
            if QUEUE_DEAD in str(call)
        ]
        assert len(dead_calls) > 0


# ==================== TESTS: Queue Service - Management ====================

class TestQueueServiceManagement:
    """Tests para gestion de jobs."""

    @pytest.mark.asyncio
    async def test_get_job(self, queue_service, sample_job, mock_redis):
        """Debe obtener job por ID."""
        mock_redis.get.return_value = json.dumps(sample_job.to_redis_dict())

        job = await queue_service.get_job(sample_job.id)

        assert job is not None
        assert job.id == sample_job.id

    @pytest.mark.asyncio
    async def test_cancel_job(self, queue_service, sample_job, mock_redis):
        """Debe cancelar job pendiente."""
        sample_job.status = JobStatus.PENDING
        mock_redis.get.return_value = json.dumps(sample_job.to_redis_dict())

        result = await queue_service.cancel_job(sample_job.id)

        assert result is True
        mock_redis.zrem.assert_called()

    @pytest.mark.asyncio
    async def test_cancel_job_processing_fails(self, queue_service, sample_job, mock_redis):
        """No debe cancelar job en procesamiento."""
        sample_job.status = JobStatus.PROCESSING
        mock_redis.get.return_value = json.dumps(sample_job.to_redis_dict())

        result = await queue_service.cancel_job(sample_job.id)

        assert result is False


# ==================== TESTS: Queue Service - Stats ====================

class TestQueueServiceStats:
    """Tests para estadisticas."""

    @pytest.mark.asyncio
    async def test_get_stats(self, queue_service, mock_redis):
        """Debe obtener estadisticas de la cola."""
        mock_redis.zcard.return_value = 10
        mock_redis.scard.return_value = 2
        mock_redis.llen.return_value = 100
        mock_redis.hgetall.return_value = {
            "total_completed": "500",
            "total_failed": "20",
            "type:spei_payment": "300",
        }
        mock_redis.lrange.return_value = ["100", "150", "200"]

        stats = await queue_service.get_stats()

        assert stats.pending_count == 10
        assert stats.processing_count == 2
        assert stats.avg_processing_time_ms == 150.0
        assert stats.counts_by_type["spei_payment"] == 300


# ==================== TESTS: Queue Service - Cleanup ====================

class TestQueueServiceCleanup:
    """Tests para limpieza de jobs."""

    @pytest.mark.asyncio
    async def test_cleanup_stale_jobs(self, queue_service, sample_job, mock_redis):
        """Debe limpiar jobs huerfanos."""
        # Simular job huerfano (locked_at expirado)
        sample_job.status = JobStatus.PROCESSING
        sample_job.locked_at = datetime.utcnow() - timedelta(minutes=10)
        sample_job.lock_timeout_seconds = 300

        mock_redis.smembers.return_value = {sample_job.id}
        mock_redis.get.return_value = json.dumps(sample_job.to_redis_dict())

        count = await queue_service.cleanup_stale_jobs()

        assert count == 1


# ==================== TESTS: Job Creation Helpers ====================

class TestJobCreationHelpers:
    """Tests para helpers de creacion de jobs."""

    def test_create_spei_payment_job(self):
        """Debe crear job de SPEI correctamente."""
        request = CreateSPEIPaymentJob(
            remittance_id="rem_123",
            clabe="012180015678912345",
            beneficiary_name="JUAN PEREZ",
            amount=Decimal("1500.50"),
            concept="PAGO REMESA",
        )

        job = request.to_job()

        assert job.type == JobType.SPEI_PAYMENT
        assert job.priority == JobPriority.HIGH
        assert job.remittance_id == "rem_123"
        assert job.payload.data["clabe"] == "012180015678912345"
        assert job.payload.data["amount"] == "1500.50"
        assert job.retry_config.max_retries == 5
        assert job.expires_at is not None

    def test_create_bitso_conversion_job(self):
        """Debe crear job de conversion Bitso correctamente."""
        request = CreateBitsoConversionJob(
            remittance_id="rem_456",
            amount_usdc=Decimal("100"),
        )

        job = request.to_job()

        assert job.type == JobType.BITSO_CONVERSION
        assert job.remittance_id == "rem_456"
        assert job.payload.data["amount_usdc"] == "100"
        assert job.retry_config.max_retries == 3


# ==================== TESTS: Dead Letter Queue ====================

class TestDeadLetterQueue:
    """Tests para dead letter queue."""

    def test_dead_letter_entry_serialization(self, sample_job):
        """DeadLetterEntry debe serializarse correctamente."""
        entry = DeadLetterEntry(
            job=sample_job,
            reason="Max retries exceeded",
            original_queue=QUEUE_PENDING,
        )

        data = entry.to_dict()
        restored = DeadLetterEntry.from_dict(data)

        assert restored.job.id == sample_job.id
        assert restored.reason == "Max retries exceeded"
        assert restored.can_replay is True

    @pytest.mark.asyncio
    async def test_get_dead_letter_jobs(self, queue_service, sample_job, mock_redis):
        """Debe obtener jobs de dead letter queue."""
        entry = DeadLetterEntry(
            job=sample_job,
            reason="Test error",
            original_queue=QUEUE_PENDING,
        )
        mock_redis.lrange.return_value = [json.dumps(entry.to_dict())]

        entries = await queue_service.get_dead_letter_jobs()

        assert len(entries) == 1
        assert entries[0].job.id == sample_job.id

    @pytest.mark.asyncio
    async def test_retry_dead_job(self, queue_service, sample_job, mock_redis):
        """Debe reintentar job de dead letter."""
        entry = DeadLetterEntry(
            job=sample_job,
            reason="Test error",
            original_queue=QUEUE_PENDING,
            can_replay=True,
        )
        mock_redis.lrange.return_value = [json.dumps(entry.to_dict())]

        result = await queue_service.retry_dead_job(sample_job.id)

        assert result is True
        mock_redis.lrem.assert_called()


# ==================== TESTS: Worker Management ====================

class TestWorkerManagement:
    """Tests para gestion de workers."""

    @pytest.mark.asyncio
    async def test_register_worker(self, queue_service, mock_redis):
        """Debe registrar worker correctamente."""
        worker = WorkerInfo(
            id="worker-1",
            hostname="localhost",
            pid=12345,
        )

        await queue_service.register_worker(worker)

        mock_redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_update_worker_heartbeat(self, queue_service, mock_redis):
        """Debe actualizar heartbeat de worker."""
        heartbeat = WorkerHeartbeat(
            worker_id="worker-1",
            status="running",
            current_job_id="job-123",
        )

        await queue_service.update_worker_heartbeat(heartbeat)

        mock_redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_get_active_workers(self, queue_service, mock_redis):
        """Debe obtener workers activos."""
        now = datetime.utcnow()
        mock_redis.hgetall.side_effect = [
            {  # registry
                "worker-1": json.dumps({
                    "id": "worker-1",
                    "hostname": "host1",
                    "pid": 123,
                    "started_at": now.isoformat(),
                    "status": "running",
                })
            },
            {  # heartbeats
                "worker-1": json.dumps({
                    "timestamp": now.isoformat(),
                    "status": "running",
                })
            }
        ]

        workers = await queue_service.get_active_workers()

        assert len(workers) == 1
        assert workers[0].id == "worker-1"
        assert workers[0].is_alive is True


# ==================== TESTS: WorkerInfo Model ====================

class TestWorkerInfoModel:
    """Tests para el modelo WorkerInfo."""

    def test_worker_is_alive_true(self):
        """Worker con heartbeat reciente debe estar vivo."""
        worker = WorkerInfo(
            id="worker-1",
            hostname="localhost",
            pid=12345,
            last_heartbeat=datetime.utcnow(),
        )

        assert worker.is_alive is True

    def test_worker_is_alive_false(self):
        """Worker sin heartbeat reciente debe estar muerto."""
        worker = WorkerInfo(
            id="worker-1",
            hostname="localhost",
            pid=12345,
            last_heartbeat=datetime.utcnow() - timedelta(seconds=60),
        )

        assert worker.is_alive is False
