"""
Worker de Procesamiento de Jobs.

Ejecuta jobs de la cola de forma asincrona con:
- Procesamiento paralelo configurable
- Heartbeat automatico
- Graceful shutdown
- Handlers por tipo de job

Uso:
    python -m app.workers.job_worker --concurrency 4
"""
import logging
import asyncio
import signal
import socket
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Callable, Awaitable, Any, List, Set
from dataclasses import dataclass
import argparse
import traceback

# Agregar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.job_queue_service import (
    JobQueueService,
    get_job_queue_service,
)
from app.schemas.job_queue import (
    Job,
    JobType,
    JobStatus,
    WorkerInfo,
    WorkerHeartbeat,
)

logger = logging.getLogger(__name__)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# ============ Job Handler Type ============

JobHandler = Callable[[Job], Awaitable[Dict[str, Any]]]


# ============ Job Handlers ============

async def handle_spei_payment(job: Job) -> Dict[str, Any]:
    """Procesa un pago SPEI."""
    from decimal import Decimal
    from app.services.stp_service import get_stp_service
    from app.core.database import get_db_session

    payload = job.payload.data
    clabe = payload.get("clabe")
    beneficiary_name = payload.get("beneficiary_name")
    amount = Decimal(payload.get("amount", "0"))
    concept = payload.get("concept", "PAGO REMESA")

    logger.info(f"Procesando SPEI: {amount} MXN a {clabe[:6]}...")

    async with get_db_session() as db:
        stp_service = get_stp_service(db)

        result = await stp_service.send_spei_payment(
            beneficiary_clabe=clabe,
            beneficiary_name=beneficiary_name,
            amount=amount,
            concept=concept,
            remittance_id=job.remittance_id,
        )

        if result.status.value in ["sent", "liquidated"]:
            return {
                "success": True,
                "tracking_key": result.tracking_key,
                "stp_id": result.stp_id,
            }
        else:
            raise Exception(
                f"SPEI falló: {result.error_message or result.status_description}"
            )


async def handle_bitso_conversion(job: Job) -> Dict[str, Any]:
    """Procesa una conversion USDC -> MXN en Bitso."""
    from decimal import Decimal
    from app.services.bitso_service import BitsoService, BitsoConfig
    from app.core.config import settings

    payload = job.payload.data
    amount_usdc = Decimal(payload.get("amount_usdc", "0"))

    logger.info(f"Procesando conversion Bitso: {amount_usdc} USDC")

    config = BitsoConfig(
        api_key=settings.BITSO_API_KEY,
        api_secret=settings.BITSO_API_SECRET,
        use_production=settings.BITSO_USE_PRODUCTION,
    )
    bitso = BitsoService(config)

    result = await bitso.convert_to_mxn(amount_usdc)

    if result.success:
        return {
            "success": True,
            "order_id": result.order_id,
            "mxn_amount": str(result.to_amount),
            "rate": str(result.rate),
        }
    else:
        raise Exception(f"Conversion Bitso falló: {result.error}")


async def handle_bitso_withdrawal(job: Job) -> Dict[str, Any]:
    """Procesa un retiro SPEI desde Bitso."""
    from decimal import Decimal
    from app.services.bitso_service import BitsoService, BitsoConfig
    from app.core.config import settings

    payload = job.payload.data
    amount = Decimal(payload.get("amount", "0"))
    clabe = payload.get("clabe")
    beneficiary_name = payload.get("beneficiary_name")
    notes_ref = payload.get("notes_ref", "PAGO")

    logger.info(f"Procesando retiro Bitso: {amount} MXN a {clabe[:6]}...")

    config = BitsoConfig(
        api_key=settings.BITSO_API_KEY,
        api_secret=settings.BITSO_API_SECRET,
        use_production=settings.BITSO_USE_PRODUCTION,
    )
    bitso = BitsoService(config)

    withdrawal = await bitso.withdraw_spei(
        amount=amount,
        clabe=clabe,
        beneficiary_name=beneficiary_name,
        notes_ref=notes_ref,
    )

    return {
        "success": True,
        "wid": withdrawal.wid,
        "status": withdrawal.status.value,
    }


async def handle_webhook_delivery(job: Job) -> Dict[str, Any]:
    """Entrega un webhook."""
    import aiohttp

    payload = job.payload.data
    url = payload.get("url")
    body = payload.get("payload", {})
    headers = payload.get("headers", {})

    logger.info(f"Entregando webhook a {url}")

    headers.setdefault("Content-Type", "application/json")
    headers.setdefault("User-Agent", "FinCore-Webhook/1.0")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=body,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status >= 200 and response.status < 300:
                return {
                    "success": True,
                    "status_code": response.status,
                }
            else:
                raise Exception(
                    f"Webhook failed: HTTP {response.status}"
                )


async def handle_compliance_screening(job: Job) -> Dict[str, Any]:
    """Ejecuta screening de compliance."""
    from app.services.compliance_screening_service import get_compliance_screening_service
    from app.schemas.compliance_screening import BlockchainNetwork
    from app.core.database import get_db_session

    payload = job.payload.data
    address = payload.get("address")
    network = BlockchainNetwork(payload.get("network", "polygon"))

    logger.info(f"Ejecutando screening para {address[:10]}...")

    async with get_db_session() as db:
        service = get_compliance_screening_service(db)

        result = await service.screen_address_for_remittance(
            address=address,
            network=network,
            remittance_id=job.remittance_id,
            user_id=job.user_id,
            amount_usd=payload.get("amount_usd"),
            direction=payload.get("direction", "inbound"),
        )

        return {
            "success": True,
            "can_proceed": result.can_proceed,
            "risk_score": result.risk_score,
            "action": result.action.value,
        }


async def handle_notification_email(job: Job) -> Dict[str, Any]:
    """Envia notificacion por email."""
    from app.services.notification_service import NotificationService

    payload = job.payload.data
    to_email = payload.get("to")
    subject = payload.get("subject")
    body = payload.get("body")
    template = payload.get("template")

    logger.info(f"Enviando email a {to_email}")

    # Implementar envio de email
    # notification_service.send_email(to_email, subject, body, template)

    return {"success": True, "sent_to": to_email}


async def handle_generic(job: Job) -> Dict[str, Any]:
    """Handler generico para jobs sin handler especifico."""
    logger.warning(f"Job {job.id} sin handler especifico, tipo: {job.type}")
    return {"success": True, "message": "No handler defined"}


# ============ Handler Registry ============

JOB_HANDLERS: Dict[JobType, JobHandler] = {
    JobType.SPEI_PAYMENT: handle_spei_payment,
    JobType.BITSO_CONVERSION: handle_bitso_conversion,
    JobType.BITSO_WITHDRAWAL: handle_bitso_withdrawal,
    JobType.WEBHOOK_DELIVERY: handle_webhook_delivery,
    JobType.COMPLIANCE_SCREENING: handle_compliance_screening,
    JobType.NOTIFICATION_EMAIL: handle_notification_email,
    JobType.GENERIC: handle_generic,
}


# ============ Worker Class ============

class JobWorker:
    """
    Worker que procesa jobs de la cola.

    Caracteristicas:
    - Concurrencia configurable
    - Heartbeat automatico
    - Graceful shutdown
    - Reintentos automaticos via cola
    """

    def __init__(
        self,
        concurrency: int = 4,
        job_types: Optional[List[JobType]] = None,
        poll_interval: float = 1.0,
        heartbeat_interval: float = 10.0,
    ):
        self.concurrency = concurrency
        self.job_types = job_types
        self.poll_interval = poll_interval
        self.heartbeat_interval = heartbeat_interval

        self.worker_id = f"{socket.gethostname()}-{os.getpid()}"
        self.hostname = socket.gethostname()
        self.pid = os.getpid()

        self.queue_service: Optional[JobQueueService] = None
        self.running = False
        self.paused = False
        self.current_jobs: Set[str] = set()
        self.stats = {
            "jobs_processed": 0,
            "jobs_failed": 0,
            "started_at": None,
        }

        self._shutdown_event = asyncio.Event()
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        """Inicia el worker."""
        logger.info(f"Iniciando worker {self.worker_id}")
        logger.info(f"Concurrencia: {self.concurrency}")
        logger.info(f"Tipos de jobs: {self.job_types or 'todos'}")

        self.running = True
        self.stats["started_at"] = datetime.utcnow()

        # Conectar a cola
        self.queue_service = await get_job_queue_service()

        # Registrar worker
        worker_info = WorkerInfo(
            id=self.worker_id,
            hostname=self.hostname,
            pid=self.pid,
            status="running",
        )
        await self.queue_service.register_worker(worker_info)

        # Configurar signal handlers
        self._setup_signals()

        # Iniciar tareas
        self._tasks = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._cleanup_loop()),
        ]

        # Iniciar workers de procesamiento
        for i in range(self.concurrency):
            task = asyncio.create_task(self._process_loop(i))
            self._tasks.append(task)

        logger.info(f"Worker {self.worker_id} iniciado con {self.concurrency} procesadores")

        # Esperar shutdown
        await self._shutdown_event.wait()

        # Cleanup
        await self._shutdown()

    async def _process_loop(self, worker_num: int) -> None:
        """Loop de procesamiento de jobs."""
        logger.info(f"Procesador {worker_num} iniciado")

        while self.running:
            if self.paused:
                await asyncio.sleep(1)
                continue

            try:
                # Obtener siguiente job
                job = await self.queue_service.dequeue(
                    worker_id=self.worker_id,
                    job_types=self.job_types,
                    timeout=int(self.poll_interval),
                )

                if job is None:
                    continue

                self.current_jobs.add(job.id)

                try:
                    await self._process_job(job)
                finally:
                    self.current_jobs.discard(job.id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en process loop: {e}")
                await asyncio.sleep(1)

        logger.info(f"Procesador {worker_num} detenido")

    async def _process_job(self, job: Job) -> None:
        """Procesa un job individual."""
        logger.info(f"Procesando job {job.id} ({job.type.value})")

        start_time = datetime.utcnow()

        try:
            # Obtener handler
            handler = JOB_HANDLERS.get(job.type, handle_generic)

            # Ejecutar con timeout
            result = await asyncio.wait_for(
                handler(job),
                timeout=job.lock_timeout_seconds
            )

            # Marcar como completado
            await self.queue_service.complete_job(job.id, result)

            self.stats["jobs_processed"] += 1

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Job {job.id} completado en {duration:.2f}s")

        except asyncio.TimeoutError:
            error = f"Job timeout after {job.lock_timeout_seconds}s"
            logger.error(f"Job {job.id}: {error}")
            await self.queue_service.fail_job(job.id, error)
            self.stats["jobs_failed"] += 1

        except Exception as e:
            error = str(e)
            details = {"traceback": traceback.format_exc()}
            logger.error(f"Job {job.id} fallido: {error}")
            await self.queue_service.fail_job(job.id, error, details)
            self.stats["jobs_failed"] += 1

    async def _heartbeat_loop(self) -> None:
        """Loop de heartbeat."""
        while self.running:
            try:
                heartbeat = WorkerHeartbeat(
                    worker_id=self.worker_id,
                    status="paused" if self.paused else "running",
                    current_job_id=next(iter(self.current_jobs), None),
                )

                await self.queue_service.update_worker_heartbeat(heartbeat)

            except Exception as e:
                logger.error(f"Error en heartbeat: {e}")

            await asyncio.sleep(self.heartbeat_interval)

    async def _cleanup_loop(self) -> None:
        """Loop de limpieza de jobs huerfanos."""
        while self.running:
            try:
                await self.queue_service.cleanup_stale_jobs()
            except Exception as e:
                logger.error(f"Error en cleanup: {e}")

            # Ejecutar cada 60 segundos
            await asyncio.sleep(60)

    def _setup_signals(self) -> None:
        """Configura manejadores de signals."""
        loop = asyncio.get_event_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self._handle_signal(s))
            )

    async def _handle_signal(self, sig: signal.Signals) -> None:
        """Maneja signals de shutdown."""
        logger.info(f"Recibido signal {sig.name}, iniciando shutdown...")
        self._shutdown_event.set()

    async def _shutdown(self) -> None:
        """Ejecuta shutdown graceful."""
        logger.info("Iniciando shutdown graceful...")

        self.running = False

        # Esperar a que terminen los jobs actuales
        if self.current_jobs:
            logger.info(f"Esperando {len(self.current_jobs)} jobs en progreso...")
            await asyncio.sleep(5)  # Dar tiempo para terminar

        # Cancelar tareas
        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)

        # Desconectar
        if self.queue_service:
            await self.queue_service.disconnect()

        logger.info(f"Worker {self.worker_id} detenido")
        logger.info(f"Stats: processed={self.stats['jobs_processed']}, "
                   f"failed={self.stats['jobs_failed']}")

    def pause(self) -> None:
        """Pausa el procesamiento de jobs."""
        self.paused = True
        logger.info("Worker pausado")

    def resume(self) -> None:
        """Reanuda el procesamiento de jobs."""
        self.paused = False
        logger.info("Worker reanudado")


# ============ CLI Entry Point ============

def main():
    """Entry point del worker."""
    parser = argparse.ArgumentParser(description="FinCore Job Worker")
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=4,
        help="Numero de procesadores concurrentes"
    )
    parser.add_argument(
        "--types", "-t",
        type=str,
        nargs="+",
        help="Tipos de jobs a procesar (ej: spei_payment bitso_conversion)"
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Intervalo de polling en segundos"
    )

    args = parser.parse_args()

    # Parsear tipos de job
    job_types = None
    if args.types:
        job_types = [JobType(t) for t in args.types]

    # Crear y ejecutar worker
    worker = JobWorker(
        concurrency=args.concurrency,
        job_types=job_types,
        poll_interval=args.poll_interval,
    )

    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
