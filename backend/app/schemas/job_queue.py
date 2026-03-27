"""
Schemas para el sistema de colas de trabajos.

Define los modelos para:
- Jobs/tareas a procesar
- Estados y prioridades
- Configuracion de reintentos
- Dead letter queue
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from enum import Enum
import uuid
import json


class JobType(str, Enum):
    """Tipos de trabajos soportados."""
    # Pagos
    SPEI_PAYMENT = "spei_payment"
    BITSO_CONVERSION = "bitso_conversion"
    BITSO_WITHDRAWAL = "bitso_withdrawal"

    # Blockchain
    BLOCKCHAIN_TX = "blockchain_tx"
    ESCROW_RELEASE = "escrow_release"
    ESCROW_REFUND = "escrow_refund"

    # Compliance
    COMPLIANCE_SCREENING = "compliance_screening"
    SAR_REPORT = "sar_report"

    # Notificaciones
    NOTIFICATION_EMAIL = "notification_email"
    NOTIFICATION_SMS = "notification_sms"
    NOTIFICATION_PUSH = "notification_push"
    WEBHOOK_DELIVERY = "webhook_delivery"

    # Reconciliacion
    RECONCILIATION = "reconciliation"

    # Genericos
    GENERIC = "generic"


class JobStatus(str, Enum):
    """Estados de un job."""
    PENDING = "pending"           # En cola, esperando procesamiento
    PROCESSING = "processing"     # Siendo procesado actualmente
    COMPLETED = "completed"       # Completado exitosamente
    FAILED = "failed"             # Fallo (puede reintentar)
    DEAD = "dead"                 # En dead letter queue (sin reintentos)
    CANCELLED = "cancelled"       # Cancelado manualmente
    SCHEDULED = "scheduled"       # Programado para futuro


class JobPriority(int, Enum):
    """Prioridades de jobs (menor numero = mayor prioridad)."""
    CRITICAL = 1      # Emergencias, bloqueos de fondos
    HIGH = 2          # Pagos activos
    NORMAL = 3        # Operaciones estandar
    LOW = 4           # Tareas de mantenimiento
    BACKGROUND = 5    # Reconciliacion, reportes


class RetryStrategy(str, Enum):
    """Estrategias de reintento."""
    EXPONENTIAL = "exponential"   # Backoff exponencial (1s, 2s, 4s, 8s...)
    LINEAR = "linear"             # Incremento lineal (1s, 2s, 3s, 4s...)
    FIXED = "fixed"               # Intervalo fijo
    FIBONACCI = "fibonacci"       # Secuencia fibonacci (1s, 1s, 2s, 3s, 5s...)


# ============ Core Models ============

class RetryConfig(BaseModel):
    """Configuracion de reintentos para un job."""
    max_retries: int = Field(default=5, ge=0, le=20)
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay_seconds: int = Field(default=5, ge=1, le=3600)
    max_delay_seconds: int = Field(default=3600, ge=1, le=86400)  # Max 24h
    jitter: bool = True  # Agregar variacion aleatoria

    def calculate_delay(self, attempt: int) -> int:
        """Calcula el delay para el proximo reintento."""
        if self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay_seconds * (2 ** attempt)
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay_seconds * (attempt + 1)
        elif self.strategy == RetryStrategy.FIBONACCI:
            delay = self._fibonacci_delay(attempt)
        else:  # FIXED
            delay = self.base_delay_seconds

        # Aplicar limite maximo
        delay = min(delay, self.max_delay_seconds)

        # Agregar jitter (variacion +/- 10%)
        if self.jitter:
            import random
            jitter_range = delay * 0.1
            delay = delay + random.uniform(-jitter_range, jitter_range)

        return max(1, int(delay))

    def _fibonacci_delay(self, n: int) -> int:
        """Calcula delay usando secuencia fibonacci."""
        if n <= 1:
            return self.base_delay_seconds
        a, b = 1, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return self.base_delay_seconds * b


class JobPayload(BaseModel):
    """Payload generico de un job."""
    data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value


class Job(BaseModel):
    """Modelo principal de un job en la cola."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: JobType
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL

    # Payload
    payload: JobPayload = Field(default_factory=JobPayload)

    # Relaciones
    remittance_id: Optional[str] = None
    user_id: Optional[str] = None
    correlation_id: Optional[str] = None  # Para agrupar jobs relacionados

    # Reintentos
    retry_config: RetryConfig = Field(default_factory=RetryConfig)
    attempts: int = 0
    last_error: Optional[str] = None
    error_history: List[Dict[str, Any]] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    scheduled_at: Optional[datetime] = None  # Para jobs programados
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # TTL del job

    # Worker info
    worker_id: Optional[str] = None
    locked_at: Optional[datetime] = None
    lock_timeout_seconds: int = 300  # 5 minutos por defecto

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
        }

    @property
    def can_retry(self) -> bool:
        """Verifica si el job puede reintentarse."""
        return (
            self.status == JobStatus.FAILED and
            self.attempts < self.retry_config.max_retries
        )

    @property
    def is_expired(self) -> bool:
        """Verifica si el job ha expirado."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_locked(self) -> bool:
        """Verifica si el job esta bloqueado por un worker."""
        if self.locked_at is None:
            return False
        lock_expires = self.locked_at + timedelta(seconds=self.lock_timeout_seconds)
        return datetime.utcnow() < lock_expires

    def to_redis_dict(self) -> Dict[str, Any]:
        """Serializa para almacenar en Redis."""
        return {
            "id": self.id,
            "type": self.type.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "payload": self.payload.model_dump(),
            "remittance_id": self.remittance_id,
            "user_id": self.user_id,
            "correlation_id": self.correlation_id,
            "retry_config": self.retry_config.model_dump(),
            "attempts": self.attempts,
            "last_error": self.last_error,
            "error_history": self.error_history,
            "created_at": self.created_at.isoformat(),
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "worker_id": self.worker_id,
            "locked_at": self.locked_at.isoformat() if self.locked_at else None,
            "lock_timeout_seconds": self.lock_timeout_seconds,
        }

    @classmethod
    def from_redis_dict(cls, data: Dict[str, Any]) -> "Job":
        """Deserializa desde Redis."""
        # Parsear datetimes
        for field in ["created_at", "scheduled_at", "started_at", "completed_at",
                      "next_retry_at", "expires_at", "locked_at"]:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        # Parsear enums
        data["type"] = JobType(data["type"])
        data["status"] = JobStatus(data["status"])
        data["priority"] = JobPriority(data["priority"])

        # Parsear nested objects
        data["payload"] = JobPayload(**data["payload"])
        data["retry_config"] = RetryConfig(**data["retry_config"])

        return cls(**data)

    def record_error(self, error: str, details: Optional[Dict] = None) -> None:
        """Registra un error en el historial."""
        self.last_error = error
        self.error_history.append({
            "attempt": self.attempts,
            "error": error,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
        })


# ============ Job Creation Helpers ============

class CreateSPEIPaymentJob(BaseModel):
    """Request para crear job de pago SPEI."""
    remittance_id: str
    clabe: str = Field(..., min_length=18, max_length=18)
    beneficiary_name: str = Field(..., min_length=1, max_length=40)
    amount: Decimal = Field(..., gt=0)
    concept: str = Field(default="PAGO REMESA")
    priority: JobPriority = JobPriority.HIGH

    def to_job(self) -> Job:
        return Job(
            type=JobType.SPEI_PAYMENT,
            priority=self.priority,
            remittance_id=self.remittance_id,
            payload=JobPayload(data={
                "clabe": self.clabe,
                "beneficiary_name": self.beneficiary_name,
                "amount": str(self.amount),
                "concept": self.concept,
            }),
            retry_config=RetryConfig(
                max_retries=5,
                strategy=RetryStrategy.EXPONENTIAL,
                base_delay_seconds=30,  # Esperar 30s antes de reintentar SPEI
                max_delay_seconds=1800,  # Max 30 minutos
            ),
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )


class CreateBitsoConversionJob(BaseModel):
    """Request para crear job de conversion Bitso."""
    remittance_id: str
    amount_usdc: Decimal = Field(..., gt=0)
    priority: JobPriority = JobPriority.HIGH

    def to_job(self) -> Job:
        return Job(
            type=JobType.BITSO_CONVERSION,
            priority=self.priority,
            remittance_id=self.remittance_id,
            payload=JobPayload(data={
                "amount_usdc": str(self.amount_usdc),
            }),
            retry_config=RetryConfig(
                max_retries=3,
                strategy=RetryStrategy.EXPONENTIAL,
                base_delay_seconds=10,
                max_delay_seconds=300,  # Max 5 minutos
            ),
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )


class CreateWebhookDeliveryJob(BaseModel):
    """Request para crear job de entrega de webhook."""
    url: str
    payload: Dict[str, Any]
    headers: Dict[str, str] = Field(default_factory=dict)
    correlation_id: Optional[str] = None

    def to_job(self) -> Job:
        return Job(
            type=JobType.WEBHOOK_DELIVERY,
            priority=JobPriority.NORMAL,
            correlation_id=self.correlation_id,
            payload=JobPayload(data={
                "url": self.url,
                "payload": self.payload,
                "headers": self.headers,
            }),
            retry_config=RetryConfig(
                max_retries=5,
                strategy=RetryStrategy.EXPONENTIAL,
                base_delay_seconds=5,
                max_delay_seconds=3600,
            ),
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )


# ============ Queue Stats ============

class QueueStats(BaseModel):
    """Estadisticas de la cola."""
    queue_name: str
    pending_count: int = 0
    processing_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    dead_count: int = 0
    scheduled_count: int = 0

    # Por tipo de job
    counts_by_type: Dict[str, int] = Field(default_factory=dict)

    # Por prioridad
    counts_by_priority: Dict[str, int] = Field(default_factory=dict)

    # Metricas de rendimiento
    avg_processing_time_ms: float = 0
    jobs_per_minute: float = 0
    error_rate: float = 0

    # Timestamps
    oldest_pending_job: Optional[datetime] = None
    last_completed_at: Optional[datetime] = None

    @property
    def total_jobs(self) -> int:
        return (
            self.pending_count +
            self.processing_count +
            self.completed_count +
            self.failed_count +
            self.dead_count
        )


class DeadLetterEntry(BaseModel):
    """Entrada en la dead letter queue."""
    job: Job
    reason: str
    moved_at: datetime = Field(default_factory=datetime.utcnow)
    original_queue: str
    can_replay: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job": self.job.to_redis_dict(),
            "reason": self.reason,
            "moved_at": self.moved_at.isoformat(),
            "original_queue": self.original_queue,
            "can_replay": self.can_replay,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeadLetterEntry":
        data["job"] = Job.from_redis_dict(data["job"])
        data["moved_at"] = datetime.fromisoformat(data["moved_at"])
        return cls(**data)


# ============ Worker Models ============

class WorkerInfo(BaseModel):
    """Informacion de un worker."""
    id: str
    hostname: str
    pid: int
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    jobs_processed: int = 0
    jobs_failed: int = 0
    current_job_id: Optional[str] = None
    status: str = "idle"  # idle, processing, paused, stopped

    @property
    def is_alive(self) -> bool:
        """Worker esta vivo si heartbeat < 30 segundos."""
        return (datetime.utcnow() - self.last_heartbeat).total_seconds() < 30


class WorkerHeartbeat(BaseModel):
    """Heartbeat de un worker."""
    worker_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str
    current_job_id: Optional[str] = None
    memory_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
