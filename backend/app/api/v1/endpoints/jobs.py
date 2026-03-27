"""
API Endpoints para el sistema de colas de jobs.

Proporciona:
- Estadisticas de la cola
- Gestion de dead letter queue
- Monitoreo de workers
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.services.job_queue_service import (
    get_job_queue_service,
    JobQueueService,
)
from app.schemas.job_queue import (
    Job,
    JobType,
    JobStatus,
    QueueStats,
    DeadLetterEntry,
    WorkerInfo,
)

router = APIRouter(prefix="/jobs", tags=["Job Queue"])


# ============ Response Models ============

class JobResponse(BaseModel):
    """Respuesta de job."""
    id: str
    type: str
    status: str
    priority: int
    attempts: int
    created_at: datetime
    remittance_id: Optional[str] = None
    last_error: Optional[str] = None

    @classmethod
    def from_job(cls, job: Job) -> "JobResponse":
        return cls(
            id=job.id,
            type=job.type.value,
            status=job.status.value,
            priority=job.priority.value,
            attempts=job.attempts,
            created_at=job.created_at,
            remittance_id=job.remittance_id,
            last_error=job.last_error,
        )


class QueueStatsResponse(BaseModel):
    """Respuesta de estadisticas."""
    queue_name: str
    pending_count: int
    processing_count: int
    completed_count: int
    failed_count: int
    dead_count: int
    scheduled_count: int
    total_jobs: int
    avg_processing_time_ms: float
    error_rate: float
    counts_by_type: dict
    oldest_pending_job: Optional[datetime]


class DeadLetterResponse(BaseModel):
    """Respuesta de dead letter."""
    job_id: str
    job_type: str
    reason: str
    moved_at: datetime
    attempts: int
    last_error: Optional[str]
    can_replay: bool


class WorkerResponse(BaseModel):
    """Respuesta de worker."""
    id: str
    hostname: str
    status: str
    started_at: datetime
    last_heartbeat: datetime
    current_job_id: Optional[str]
    is_alive: bool


# ============ Endpoints ============

@router.get("/stats", response_model=QueueStatsResponse)
async def get_queue_stats():
    """Obtiene estadisticas de la cola de jobs."""
    try:
        queue_service = await get_job_queue_service()
        stats = await queue_service.get_stats()

        return QueueStatsResponse(
            queue_name=stats.queue_name,
            pending_count=stats.pending_count,
            processing_count=stats.processing_count,
            completed_count=stats.completed_count,
            failed_count=stats.failed_count,
            dead_count=stats.dead_count,
            scheduled_count=stats.scheduled_count,
            total_jobs=stats.total_jobs,
            avg_processing_time_ms=stats.avg_processing_time_ms,
            error_rate=stats.error_rate,
            counts_by_type=stats.counts_by_type,
            oldest_pending_job=stats.oldest_pending_job,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Obtiene un job por ID."""
    try:
        queue_service = await get_job_queue_service()
        job = await queue_service.get_job(job_id)

        if job is None:
            raise HTTPException(status_code=404, detail="Job no encontrado")

        return JobResponse.from_job(job)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancela un job pendiente."""
    try:
        queue_service = await get_job_queue_service()
        success = await queue_service.cancel_job(job_id)

        if not success:
            raise HTTPException(
                status_code=400,
                detail="No se puede cancelar el job (ya procesado o en progreso)"
            )

        return {"success": True, "message": "Job cancelado"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dead-letter/list", response_model=List[DeadLetterResponse])
async def list_dead_letter_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Lista jobs en la dead letter queue."""
    try:
        queue_service = await get_job_queue_service()
        entries = await queue_service.get_dead_letter_jobs(limit, offset)

        return [
            DeadLetterResponse(
                job_id=entry.job.id,
                job_type=entry.job.type.value,
                reason=entry.reason,
                moved_at=entry.moved_at,
                attempts=entry.job.attempts,
                last_error=entry.job.last_error,
                can_replay=entry.can_replay,
            )
            for entry in entries
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dead-letter/{job_id}/retry")
async def retry_dead_letter_job(job_id: str):
    """Reintenta un job de la dead letter queue."""
    try:
        queue_service = await get_job_queue_service()
        success = await queue_service.retry_dead_job(job_id)

        if not success:
            raise HTTPException(
                status_code=400,
                detail="No se puede reintentar el job"
            )

        return {"success": True, "message": "Job reencolado para reintento"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workers/active", response_model=List[WorkerResponse])
async def list_active_workers():
    """Lista workers activos."""
    try:
        queue_service = await get_job_queue_service()
        workers = await queue_service.get_active_workers()

        return [
            WorkerResponse(
                id=w.id,
                hostname=w.hostname,
                status=w.status,
                started_at=w.started_at,
                last_heartbeat=w.last_heartbeat,
                current_job_id=w.current_job_id,
                is_alive=w.is_alive,
            )
            for w in workers
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup/stale")
async def cleanup_stale_jobs():
    """Limpia jobs huerfanos (stale)."""
    try:
        queue_service = await get_job_queue_service()
        count = await queue_service.cleanup_stale_jobs()

        return {
            "success": True,
            "cleaned_jobs": count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup/old-completed")
async def cleanup_old_completed_jobs(
    older_than_days: int = Query(default=7, ge=1, le=30)
):
    """Purga jobs completados antiguos."""
    try:
        queue_service = await get_job_queue_service()
        count = await queue_service.purge_old_completed_jobs(older_than_days)

        return {
            "success": True,
            "purged_jobs": count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
