"""
Scheduler de Jobs para FinCore.

Configura y gestiona jobs programados usando APScheduler:
- Reconciliacion automatica cada 60 minutos
- Limpieza de datos expirados
- Procesamiento de reembolsos pendientes
- Verificacion de transacciones blockchain

Uso:
    from app.core.scheduler import scheduler, start_scheduler, shutdown_scheduler

    # En startup de la aplicacion:
    start_scheduler()

    # En shutdown:
    shutdown_scheduler()
"""
import os
import logging
import asyncio
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent

from sqlalchemy.orm import Session
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


# ============ Configuracion ============

# Intervalo de reconciliacion en minutos
RECONCILIATION_INTERVAL = int(os.getenv("RECONCILIATION_INTERVAL_MINUTES", "60"))

# Intervalo de verificacion de reembolsos en minutos
REFUND_CHECK_INTERVAL = int(os.getenv("REFUND_CHECK_INTERVAL_MINUTES", "15"))

# Intervalo de verificacion de transacciones pendientes en minutos
TX_CHECK_INTERVAL = int(os.getenv("TX_CHECK_INTERVAL_MINUTES", "5"))

# Intervalo de verificacion de resubmission de transacciones atascadas
RELAYER_RESUBMIT_INTERVAL = int(os.getenv("RELAYER_RESUBMIT_INTERVAL_MINUTES", "2"))

# Timezone
TIMEZONE = os.getenv("SCHEDULER_TIMEZONE", "America/Mexico_City")


# ============ Scheduler Global ============

scheduler: Optional[AsyncIOScheduler] = None


def get_db_session() -> Session:
    """Obtiene una sesion de base de datos para los jobs."""
    return SessionLocal()


# ============ Jobs ============

async def job_reconciliation():
    """
    Job de reconciliacion automatica.

    Ejecuta cada 60 minutos:
    1. Compara saldos Ledger vs On-chain
    2. Verifica transacciones pendientes
    3. Detecta discrepancias
    4. Envia alertas si es necesario
    """
    logger.info("Iniciando job de reconciliacion programada")
    db = None

    try:
        db = get_db_session()

        from app.services.reconciliation_service import ReconciliationService

        service = ReconciliationService(db=db)
        result = await service.run_full_reconciliation(stablecoin="USDC")

        if result.success:
            logger.info(
                f"Reconciliacion completada: "
                f"discrepancias={len(result.discrepancies)}, "
                f"alertas={result.alerts_sent}"
            )
        else:
            logger.error(f"Reconciliacion fallo: {result.error}")

    except Exception as e:
        logger.error(f"Error en job de reconciliacion: {e}")

    finally:
        if db:
            db.close()


async def job_process_pending_refunds():
    """
    Job de procesamiento de reembolsos pendientes.

    Ejecuta cada 15 minutos:
    1. Busca remesas con escrow expirado (> 48h)
    2. Procesa reembolsos automaticos
    3. Actualiza estados
    """
    logger.info("Iniciando job de reembolsos pendientes")
    db = None

    try:
        db = get_db_session()

        from app.services.remittance_service import RemittanceService
        from app.models.remittance import Remittance, RemittanceStatus
        from datetime import datetime

        service = RemittanceService(db=db)

        # Obtener remesas con escrow expirado
        pending_refunds = service.get_pending_refunds()

        for remittance in pending_refunds:
            try:
                result = await service.process_refund(str(remittance.id))
                if result.success:
                    logger.info(
                        f"Reembolso procesado: {remittance.reference_code}"
                    )
                else:
                    logger.warning(
                        f"No se pudo procesar reembolso {remittance.reference_code}: "
                        f"{result.error}"
                    )
            except Exception as e:
                logger.error(
                    f"Error procesando reembolso {remittance.reference_code}: {e}"
                )

        logger.info(f"Job de reembolsos completado: {len(pending_refunds)} procesados")

    except Exception as e:
        logger.error(f"Error en job de reembolsos: {e}")

    finally:
        if db:
            db.close()


async def job_check_pending_transactions():
    """
    Job de verificacion de transacciones blockchain pendientes.

    Ejecuta cada 5 minutos:
    1. Busca transacciones en estado SUBMITTED
    2. Verifica su estado en blockchain
    3. Actualiza estados segun confirmaciones
    """
    logger.info("Iniciando job de verificacion de transacciones")
    db = None

    try:
        db = get_db_session()

        from app.models.remittance import RemittanceBlockchainTx, BlockchainRemittanceStatus
        from app.services.blockchain_service import BlockchainService
        from app.models.blockchain import BlockchainNetwork

        # Buscar transacciones pendientes de confirmacion
        pending_txs = db.query(RemittanceBlockchainTx).filter(
            RemittanceBlockchainTx.blockchain_status.in_([
                BlockchainRemittanceStatus.SUBMITTED,
                BlockchainRemittanceStatus.MINED,
            ])
        ).all()

        if not pending_txs:
            logger.debug("No hay transacciones pendientes de verificar")
            return

        blockchain_service = BlockchainService(network=BlockchainNetwork.POLYGON)

        for tx in pending_txs:
            if not tx.tx_hash:
                continue

            try:
                receipt = blockchain_service.get_transaction_receipt(tx.tx_hash)

                if receipt:
                    if receipt.get("status") == 1:
                        # Transaccion exitosa
                        current_block = blockchain_service.get_current_block()
                        confirmations = current_block - receipt.get("blockNumber", 0)

                        tx.block_number = receipt.get("blockNumber")
                        tx.gas_used = receipt.get("gasUsed")
                        tx.confirmations = confirmations

                        if confirmations >= 12:  # 12 confirmaciones = confirmado
                            tx.blockchain_status = BlockchainRemittanceStatus.CONFIRMED
                            tx.confirmed_at = datetime.utcnow()
                        else:
                            tx.blockchain_status = BlockchainRemittanceStatus.MINED

                    else:
                        # Transaccion fallida
                        tx.blockchain_status = BlockchainRemittanceStatus.REVERTED
                        tx.error_message = "Transaction reverted on-chain"

                    db.commit()
                    logger.debug(
                        f"TX {tx.tx_hash[:10]}... actualizada: {tx.blockchain_status.value}"
                    )

            except Exception as e:
                logger.error(f"Error verificando TX {tx.tx_hash}: {e}")

        logger.info(f"Job de transacciones completado: {len(pending_txs)} verificadas")

    except Exception as e:
        logger.error(f"Error en job de transacciones: {e}")

    finally:
        if db:
            db.close()


async def job_cleanup_expired_quotes():
    """
    Job de limpieza de cotizaciones expiradas.

    Ejecuta cada hora:
    Limpia datos temporales y cotizaciones viejas.
    """
    logger.info("Iniciando job de limpieza")

    # Por ahora solo log - las cotizaciones se almacenan en memoria/cache
    logger.info("Job de limpieza completado")


async def job_relayer_resubmit():
    """
    Job de re-envío de transacciones blockchain atascadas.

    Ejecuta cada 2 minutos:
    1. Busca transacciones pendientes por más de 60 segundos
    2. Re-envía con gas más alto (15% bump)
    3. Actualiza métricas de Prometheus
    """
    logger.info("Iniciando job de relayer resubmit")

    try:
        from app.services.relayer_service import RelayerService
        from app.models.blockchain import BlockchainNetwork

        relayer = RelayerService(network=BlockchainNetwork.POLYGON)

        resubmitted = await relayer.check_and_resubmit_stuck_transactions()

        if resubmitted > 0:
            logger.info(f"Relayer: {resubmitted} transacciones re-enviadas con gas mayor")
        else:
            logger.debug("Relayer: no hay transacciones atascadas")

        relayer.close()

    except Exception as e:
        logger.error(f"Error en job de relayer: {e}")


# ============ Event Handlers ============

def job_listener(event: JobExecutionEvent):
    """Listener para eventos de jobs."""
    if event.exception:
        logger.error(
            f"Job {event.job_id} fallo con excepcion: {event.exception}"
        )
    else:
        logger.debug(f"Job {event.job_id} ejecutado exitosamente")


# ============ Scheduler Control ============

def create_scheduler() -> AsyncIOScheduler:
    """Crea y configura el scheduler."""
    sched = AsyncIOScheduler(
        timezone=TIMEZONE,
        job_defaults={
            "coalesce": True,  # Combinar ejecuciones perdidas
            "max_instances": 1,  # Solo una instancia por job
            "misfire_grace_time": 60,  # Gracia de 60 segundos
        }
    )

    # Agregar listener de eventos
    sched.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

    return sched


def start_scheduler():
    """Inicia el scheduler con todos los jobs programados."""
    global scheduler

    if scheduler is not None and scheduler.running:
        logger.warning("Scheduler ya esta ejecutandose")
        return

    scheduler = create_scheduler()

    # Job 1: Reconciliacion cada 60 minutos
    scheduler.add_job(
        job_reconciliation,
        trigger=IntervalTrigger(minutes=RECONCILIATION_INTERVAL),
        id="reconciliation",
        name="Reconciliacion Ledger vs On-chain",
        replace_existing=True,
    )

    # Job 2: Verificar reembolsos cada 15 minutos
    scheduler.add_job(
        job_process_pending_refunds,
        trigger=IntervalTrigger(minutes=REFUND_CHECK_INTERVAL),
        id="pending_refunds",
        name="Procesar Reembolsos Pendientes",
        replace_existing=True,
    )

    # Job 3: Verificar transacciones cada 5 minutos
    scheduler.add_job(
        job_check_pending_transactions,
        trigger=IntervalTrigger(minutes=TX_CHECK_INTERVAL),
        id="pending_transactions",
        name="Verificar Transacciones Blockchain",
        replace_existing=True,
    )

    # Job 4: Limpieza cada hora (al minuto 30)
    scheduler.add_job(
        job_cleanup_expired_quotes,
        trigger=CronTrigger(minute=30),
        id="cleanup",
        name="Limpieza de Datos Expirados",
        replace_existing=True,
    )

    # Job 5: Relayer resubmit cada 2 minutos
    scheduler.add_job(
        job_relayer_resubmit,
        trigger=IntervalTrigger(minutes=RELAYER_RESUBMIT_INTERVAL),
        id="relayer_resubmit",
        name="Relayer - Resubmit Transacciones Atascadas",
        replace_existing=True,
    )

    scheduler.start()

    logger.info(
        f"Scheduler iniciado con {len(scheduler.get_jobs())} jobs programados"
    )
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.id}: {job.name} ({job.trigger})")


def shutdown_scheduler():
    """Detiene el scheduler de forma segura."""
    global scheduler

    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler detenido")
        scheduler = None


def get_scheduler_status() -> dict:
    """Obtiene estado actual del scheduler."""
    global scheduler

    if scheduler is None:
        return {"status": "not_initialized", "jobs": []}

    if not scheduler.running:
        return {"status": "stopped", "jobs": []}

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return {
        "status": "running",
        "timezone": str(TIMEZONE),
        "jobs": jobs,
    }


async def run_job_now(job_id: str) -> bool:
    """
    Ejecuta un job inmediatamente.

    Args:
        job_id: ID del job a ejecutar

    Returns:
        True si se ejecuto correctamente
    """
    global scheduler

    if scheduler is None or not scheduler.running:
        logger.error("Scheduler no esta ejecutandose")
        return False

    job = scheduler.get_job(job_id)
    if job is None:
        logger.error(f"Job {job_id} no encontrado")
        return False

    try:
        # Ejecutar el job directamente
        await job.func()
        return True
    except Exception as e:
        logger.error(f"Error ejecutando job {job_id}: {e}")
        return False
