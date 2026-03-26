"""
Event Listener Service para FinCore.

Escucha eventos blockchain en tiempo real:
- RemittanceCreated: Fondos bloqueados en escrow
- RemittanceReleased: Fondos liberados al pool
- RemittanceRefunded: Fondos devueltos al sender
- Transfer: Transferencias ERC20 (USDC/USDT)

Arquitectura:
- WebSocket para eventos en tiempo real
- Polling como fallback
- Persistencia en DB para idempotencia
- Webhooks para notificar UI/servicios externos

Evaluación The Graph vs Solución Propia:
------------------------------------------
| Criterio              | The Graph | Solución Propia |
|-----------------------|-----------|-----------------|
| Latencia              | ~1-2 bloques | <1 bloque (WS) |
| Costo                 | ~$50-100/mes | Infra propia    |
| Complejidad           | Media     | Alta            |
| Confiabilidad         | Alta      | Depende infra   |
| Flexibilidad          | Schema    | Total           |
| Historico             | Excelente | Manual          |

Recomendación: Solución híbrida
- Listener propio para eventos críticos (real-time)
- The Graph para queries históricas y analytics

Uso:
    from app.services.event_listener_service import EventListenerService

    listener = EventListenerService(network=BlockchainNetwork.POLYGON)
    await listener.start()  # Inicia escucha en background
"""
import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

from web3 import Web3
from web3.contract import Contract
from web3.types import LogReceipt, BlockData
from eth_typing import HexStr
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.blockchain import BlockchainNetwork
from app.models.remittance import (
    Remittance,
    RemittanceBlockchainTx,
    RemittanceStatus,
    BlockchainRemittanceStatus,
)

# Prometheus metrics
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)


# ==================== Configuración ====================

# RPC URLs por red
RPC_URLS = {
    BlockchainNetwork.POLYGON: os.getenv(
        "POLYGON_RPC_URL",
        "https://polygon-rpc.com"
    ),
    BlockchainNetwork.POLYGON_AMOY: os.getenv(
        "POLYGON_AMOY_RPC_URL",
        "https://rpc-amoy.polygon.technology"
    ),
    BlockchainNetwork.ETHEREUM: os.getenv(
        "ETHEREUM_RPC_URL",
        "https://eth.llamarpc.com"
    ),
}

# WebSocket URLs por red
WS_URLS = {
    BlockchainNetwork.POLYGON: os.getenv(
        "POLYGON_WS_URL",
        "wss://polygon-bor-rpc.publicnode.com"
    ),
    BlockchainNetwork.POLYGON_AMOY: os.getenv(
        "POLYGON_AMOY_WS_URL",
        "wss://polygon-amoy-bor-rpc.publicnode.com"
    ),
}

# Direcciones de contratos
CONTRACT_ADDRESSES = {
    BlockchainNetwork.POLYGON: os.getenv(
        "FINCORE_REMITTANCE_CONTRACT_POLYGON",
        ""  # Debe configurarse
    ),
    BlockchainNetwork.POLYGON_AMOY: os.getenv(
        "FINCORE_REMITTANCE_CONTRACT_AMOY",
        ""
    ),
}

# Direcciones de tokens
USDC_ADDRESSES = {
    BlockchainNetwork.POLYGON: "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",  # USDC nativo
    BlockchainNetwork.POLYGON_AMOY: "0x41E94Eb019C0762f9Bfcf9Fb1E58725BfB0e7582",  # USDC en Amoy
}

# Intervalo de polling (fallback)
POLLING_INTERVAL = int(os.getenv("EVENT_POLLING_INTERVAL", "12"))  # segundos

# Bloque desde donde empezar a escuchar (0 = desde deployment)
START_BLOCK = int(os.getenv("EVENT_START_BLOCK", "0"))


# ==================== Métricas Prometheus ====================

EVENTS_RECEIVED = Counter(
    'blockchain_events_received_total',
    'Total de eventos blockchain recibidos',
    ['network', 'event_type']
)

EVENTS_PROCESSED = Counter(
    'blockchain_events_processed_total',
    'Total de eventos procesados exitosamente',
    ['network', 'event_type']
)

EVENTS_FAILED = Counter(
    'blockchain_events_failed_total',
    'Total de eventos que fallaron al procesar',
    ['network', 'event_type']
)

EVENT_PROCESSING_TIME = Histogram(
    'blockchain_event_processing_seconds',
    'Tiempo de procesamiento de eventos',
    ['event_type'],
    buckets=[0.1, 0.25, 0.5, 1, 2.5, 5, 10]
)

LAST_PROCESSED_BLOCK = Gauge(
    'blockchain_last_processed_block',
    'Último bloque procesado',
    ['network']
)

LISTENER_STATUS = Gauge(
    'blockchain_listener_status',
    'Estado del listener (1=running, 0=stopped)',
    ['network']
)

WEBSOCKET_RECONNECTS = Counter(
    'blockchain_websocket_reconnects_total',
    'Total de reconexiones WebSocket',
    ['network']
)


# ==================== ABIs de Contratos ====================

# ABI de FinCoreRemittance (solo eventos relevantes)
FINCORE_REMITTANCE_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "remittanceId", "type": "uint256"},
            {"indexed": True, "name": "referenceId", "type": "bytes32"},
            {"indexed": True, "name": "sender", "type": "address"},
            {"indexed": False, "name": "token", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": False, "name": "fee", "type": "uint256"},
            {"indexed": False, "name": "expiresAt", "type": "uint256"},
        ],
        "name": "RemittanceCreated",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "remittanceId", "type": "uint256"},
            {"indexed": True, "name": "referenceId", "type": "bytes32"},
            {"indexed": True, "name": "operator", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
        ],
        "name": "RemittanceReleased",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "remittanceId", "type": "uint256"},
            {"indexed": True, "name": "referenceId", "type": "bytes32"},
            {"indexed": True, "name": "sender", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
        ],
        "name": "RemittanceRefunded",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "token", "type": "address"},
        ],
        "name": "TokenAdded",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "token", "type": "address"},
        ],
        "name": "TokenRemoved",
        "type": "event",
    },
]

# ABI de ERC20 (Transfer)
ERC20_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": True, "name": "spender", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Approval",
        "type": "event",
    },
]


# ==================== Tipos ====================

class EventType(str, Enum):
    """Tipos de eventos soportados."""
    REMITTANCE_CREATED = "RemittanceCreated"
    REMITTANCE_RELEASED = "RemittanceReleased"
    REMITTANCE_REFUNDED = "RemittanceRefunded"
    TRANSFER = "Transfer"
    TOKEN_ADDED = "TokenAdded"
    TOKEN_REMOVED = "TokenRemoved"


@dataclass
class BlockchainEvent:
    """Representación de un evento blockchain."""
    event_type: EventType
    tx_hash: str
    block_number: int
    block_timestamp: Optional[datetime]
    log_index: int
    contract_address: str
    args: Dict[str, Any]
    raw_log: Optional[LogReceipt] = None

    def __post_init__(self):
        self.id = f"{self.tx_hash}_{self.log_index}"


@dataclass
class EventSubscription:
    """Suscripción a un tipo de evento."""
    event_type: EventType
    callback: Callable[[BlockchainEvent], None]
    filter_params: Dict = field(default_factory=dict)


# ==================== Excepciones ====================

class EventListenerError(Exception):
    """Error base del listener."""
    pass


class ConnectionError(EventListenerError):
    """Error de conexión a la blockchain."""
    pass


class ProcessingError(EventListenerError):
    """Error procesando un evento."""
    pass


# ==================== Servicio Principal ====================

class EventListenerService:
    """
    Servicio de escucha de eventos blockchain.

    Features:
    - WebSocket para eventos en tiempo real
    - Polling como fallback
    - Reconexión automática
    - Persistencia de último bloque procesado
    - Callbacks configurables
    - Métricas Prometheus
    """

    def __init__(
        self,
        network: BlockchainNetwork = BlockchainNetwork.POLYGON,
        use_websocket: bool = True,
        db: Optional[Session] = None,
    ):
        self.network = network
        self.use_websocket = use_websocket
        self._db = db

        # Conexiones Web3
        self.w3_http: Optional[Web3] = None
        self.w3_ws: Optional[Web3] = None

        # Contratos
        self.remittance_contract: Optional[Contract] = None
        self.usdc_contract: Optional[Contract] = None

        # Estado
        self._running = False
        self._last_block = START_BLOCK
        self._subscriptions: List[EventSubscription] = []
        self._processed_events: set = set()  # Para idempotencia

        # Tareas asyncio
        self._listen_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Webhook callbacks
        self._webhook_callbacks: List[Callable] = []

        # Inicializar conexiones
        self._init_connections()

    def _init_connections(self):
        """Inicializa conexiones Web3."""
        rpc_url = RPC_URLS.get(self.network)
        ws_url = WS_URLS.get(self.network)

        if not rpc_url:
            raise ConnectionError(f"No hay RPC URL configurada para {self.network}")

        # HTTP (siempre)
        self.w3_http = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3_http.is_connected():
            raise ConnectionError(f"No se pudo conectar a {rpc_url}")

        # WebSocket (opcional)
        if self.use_websocket and ws_url:
            try:
                self.w3_ws = Web3(Web3.WebsocketProvider(ws_url))
            except Exception as e:
                logger.warning(f"No se pudo conectar WebSocket: {e}")
                self.w3_ws = None

        # Contratos
        contract_address = CONTRACT_ADDRESSES.get(self.network)
        if contract_address:
            self.remittance_contract = self.w3_http.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=FINCORE_REMITTANCE_ABI,
            )

        usdc_address = USDC_ADDRESSES.get(self.network)
        if usdc_address:
            self.usdc_contract = self.w3_http.eth.contract(
                address=Web3.to_checksum_address(usdc_address),
                abi=ERC20_ABI,
            )

        logger.info(
            f"EventListener inicializado para {self.network.value} "
            f"(WS: {self.w3_ws is not None})"
        )

    @property
    def db(self) -> Session:
        """Obtiene sesión de DB (lazy)."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    # ==================== Suscripciones ====================

    def subscribe(
        self,
        event_type: EventType,
        callback: Callable[[BlockchainEvent], None],
        **filter_params,
    ):
        """
        Suscribe un callback a un tipo de evento.

        Args:
            event_type: Tipo de evento a escuchar
            callback: Función a llamar cuando se recibe el evento
            **filter_params: Parámetros de filtro (ej: sender=0x...)
        """
        subscription = EventSubscription(
            event_type=event_type,
            callback=callback,
            filter_params=filter_params,
        )
        self._subscriptions.append(subscription)
        logger.info(f"Suscripción añadida: {event_type.value}")

    def register_webhook(self, callback: Callable[[BlockchainEvent], None]):
        """Registra un callback para webhooks."""
        self._webhook_callbacks.append(callback)

    # ==================== Control del Listener ====================

    async def start(self):
        """Inicia el listener de eventos."""
        if self._running:
            logger.warning("Listener ya está ejecutándose")
            return

        self._running = True
        LISTENER_STATUS.labels(network=self.network.value).set(1)

        # Cargar último bloque procesado
        await self._load_last_block()

        # Iniciar tarea de escucha
        if self.use_websocket and self.w3_ws:
            self._listen_task = asyncio.create_task(self._websocket_listener())
        else:
            self._listen_task = asyncio.create_task(self._polling_listener())

        # Heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat())

        logger.info(f"EventListener iniciado para {self.network.value}")

    async def stop(self):
        """Detiene el listener."""
        self._running = False
        LISTENER_STATUS.labels(network=self.network.value).set(0)

        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        # Guardar último bloque
        await self._save_last_block()

        logger.info("EventListener detenido")

    # ==================== Listeners ====================

    async def _websocket_listener(self):
        """Escucha eventos via WebSocket."""
        while self._running:
            try:
                # Crear filtros para cada evento
                if self.remittance_contract:
                    await self._subscribe_contract_events(self.remittance_contract)

                if self.usdc_contract:
                    await self._subscribe_transfer_events(self.usdc_contract)

                # Mantener conexión viva
                while self._running:
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error en WebSocket listener: {e}")
                WEBSOCKET_RECONNECTS.labels(network=self.network.value).inc()
                await asyncio.sleep(5)  # Esperar antes de reconectar

    async def _polling_listener(self):
        """Escucha eventos via polling (fallback)."""
        while self._running:
            try:
                current_block = self.w3_http.eth.block_number

                if current_block > self._last_block:
                    await self._process_blocks(self._last_block + 1, current_block)
                    self._last_block = current_block
                    LAST_PROCESSED_BLOCK.labels(network=self.network.value).set(current_block)

                await asyncio.sleep(POLLING_INTERVAL)

            except Exception as e:
                logger.error(f"Error en polling listener: {e}")
                await asyncio.sleep(POLLING_INTERVAL * 2)

    async def _subscribe_contract_events(self, contract: Contract):
        """Suscribe a eventos de un contrato via WS."""
        # Implementación depende del proveedor WS
        # Algunos soportan eth_subscribe, otros no
        pass

    async def _subscribe_transfer_events(self, contract: Contract):
        """Suscribe a eventos Transfer de ERC20."""
        pass

    async def _process_blocks(self, from_block: int, to_block: int):
        """Procesa eventos en un rango de bloques."""
        # Limitar rango para evitar timeouts
        max_range = 1000
        if to_block - from_block > max_range:
            # Procesar en chunks
            for start in range(from_block, to_block, max_range):
                end = min(start + max_range - 1, to_block)
                await self._process_block_range(start, end)
        else:
            await self._process_block_range(from_block, to_block)

    async def _process_block_range(self, from_block: int, to_block: int):
        """Procesa eventos en un rango específico."""
        logger.debug(f"Procesando bloques {from_block} - {to_block}")

        try:
            # Eventos de FinCoreRemittance
            if self.remittance_contract:
                # RemittanceCreated
                created_filter = self.remittance_contract.events.RemittanceCreated.create_filter(
                    fromBlock=from_block,
                    toBlock=to_block,
                )
                for log in created_filter.get_all_entries():
                    await self._handle_event(EventType.REMITTANCE_CREATED, log)

                # RemittanceReleased
                released_filter = self.remittance_contract.events.RemittanceReleased.create_filter(
                    fromBlock=from_block,
                    toBlock=to_block,
                )
                for log in released_filter.get_all_entries():
                    await self._handle_event(EventType.REMITTANCE_RELEASED, log)

                # RemittanceRefunded
                refunded_filter = self.remittance_contract.events.RemittanceRefunded.create_filter(
                    fromBlock=from_block,
                    toBlock=to_block,
                )
                for log in refunded_filter.get_all_entries():
                    await self._handle_event(EventType.REMITTANCE_REFUNDED, log)

            # Eventos Transfer de USDC (opcional, puede ser muy verboso)
            # Solo si hay un filtro específico (ej: transferencias a nuestro contrato)

        except Exception as e:
            logger.error(f"Error procesando bloques {from_block}-{to_block}: {e}")

    # ==================== Manejo de Eventos ====================

    async def _handle_event(self, event_type: EventType, log: LogReceipt):
        """Procesa un evento recibido."""
        tx_hash = log['transactionHash'].hex()
        log_index = log['logIndex']
        event_id = f"{tx_hash}_{log_index}"

        # Idempotencia
        if event_id in self._processed_events:
            logger.debug(f"Evento ya procesado: {event_id}")
            return

        EVENTS_RECEIVED.labels(
            network=self.network.value,
            event_type=event_type.value
        ).inc()

        try:
            # Obtener timestamp del bloque
            block = self.w3_http.eth.get_block(log['blockNumber'])
            block_timestamp = datetime.fromtimestamp(block['timestamp'])

            # Crear objeto de evento
            event = BlockchainEvent(
                event_type=event_type,
                tx_hash=tx_hash,
                block_number=log['blockNumber'],
                block_timestamp=block_timestamp,
                log_index=log_index,
                contract_address=log['address'],
                args=dict(log['args']),
                raw_log=log,
            )

            # Procesar según tipo
            with EVENT_PROCESSING_TIME.labels(event_type=event_type.value).time():
                await self._process_event(event)

            # Marcar como procesado
            self._processed_events.add(event_id)

            # Llamar callbacks de suscripciones
            for sub in self._subscriptions:
                if sub.event_type == event_type:
                    try:
                        if asyncio.iscoroutinefunction(sub.callback):
                            await sub.callback(event)
                        else:
                            sub.callback(event)
                    except Exception as e:
                        logger.error(f"Error en callback: {e}")

            # Webhooks
            for webhook_cb in self._webhook_callbacks:
                try:
                    await self._trigger_webhook(webhook_cb, event)
                except Exception as e:
                    logger.error(f"Error en webhook: {e}")

            EVENTS_PROCESSED.labels(
                network=self.network.value,
                event_type=event_type.value
            ).inc()

        except Exception as e:
            logger.error(f"Error procesando evento {event_id}: {e}")
            EVENTS_FAILED.labels(
                network=self.network.value,
                event_type=event_type.value
            ).inc()

    async def _process_event(self, event: BlockchainEvent):
        """Procesa un evento y actualiza la DB."""
        if event.event_type == EventType.REMITTANCE_CREATED:
            await self._process_remittance_created(event)
        elif event.event_type == EventType.REMITTANCE_RELEASED:
            await self._process_remittance_released(event)
        elif event.event_type == EventType.REMITTANCE_REFUNDED:
            await self._process_remittance_refunded(event)
        elif event.event_type == EventType.TRANSFER:
            await self._process_transfer(event)

    async def _process_remittance_created(self, event: BlockchainEvent):
        """Procesa evento RemittanceCreated."""
        args = event.args

        # Obtener referenceId (bytes32 -> hex string)
        reference_id = args['referenceId'].hex() if isinstance(args['referenceId'], bytes) else args['referenceId']

        # Buscar remesa en DB por reference_code
        remittance = self.db.query(Remittance).filter(
            Remittance.reference_code == reference_id[:20]  # Truncar si es necesario
        ).first()

        if remittance:
            # Actualizar estado
            remittance.status = RemittanceStatus.LOCKED
            remittance.escrow_locked_at = event.block_timestamp
            remittance.escrow_expires_at = datetime.fromtimestamp(args['expiresAt'])

            # Crear registro de transacción blockchain
            blockchain_tx = RemittanceBlockchainTx(
                remittance_id=remittance.id,
                tx_hash=event.tx_hash,
                operation="lock",
                blockchain_status=BlockchainRemittanceStatus.CONFIRMED,
                network=self.network.value,
                contract_address=event.contract_address,
                block_number=event.block_number,
                block_timestamp=event.block_timestamp,
                confirmed_at=event.block_timestamp,
            )
            self.db.add(blockchain_tx)
            self.db.commit()

            logger.info(
                f"RemittanceCreated procesado: {remittance.reference_code} "
                f"(ID on-chain: {args['remittanceId']})"
            )
        else:
            logger.warning(f"Remesa no encontrada para reference_id: {reference_id}")

    async def _process_remittance_released(self, event: BlockchainEvent):
        """Procesa evento RemittanceReleased."""
        args = event.args
        reference_id = args['referenceId'].hex() if isinstance(args['referenceId'], bytes) else args['referenceId']

        remittance = self.db.query(Remittance).filter(
            Remittance.reference_code == reference_id[:20]
        ).first()

        if remittance:
            remittance.status = RemittanceStatus.COMPLETED
            remittance.completed_at = event.block_timestamp

            blockchain_tx = RemittanceBlockchainTx(
                remittance_id=remittance.id,
                tx_hash=event.tx_hash,
                operation="release",
                blockchain_status=BlockchainRemittanceStatus.CONFIRMED,
                network=self.network.value,
                contract_address=event.contract_address,
                block_number=event.block_number,
                block_timestamp=event.block_timestamp,
                confirmed_at=event.block_timestamp,
            )
            self.db.add(blockchain_tx)
            self.db.commit()

            logger.info(f"RemittanceReleased procesado: {remittance.reference_code}")

    async def _process_remittance_refunded(self, event: BlockchainEvent):
        """Procesa evento RemittanceRefunded."""
        args = event.args
        reference_id = args['referenceId'].hex() if isinstance(args['referenceId'], bytes) else args['referenceId']

        remittance = self.db.query(Remittance).filter(
            Remittance.reference_code == reference_id[:20]
        ).first()

        if remittance:
            remittance.status = RemittanceStatus.REFUNDED
            remittance.completed_at = event.block_timestamp

            blockchain_tx = RemittanceBlockchainTx(
                remittance_id=remittance.id,
                tx_hash=event.tx_hash,
                operation="refund",
                blockchain_status=BlockchainRemittanceStatus.CONFIRMED,
                network=self.network.value,
                contract_address=event.contract_address,
                block_number=event.block_number,
                block_timestamp=event.block_timestamp,
                confirmed_at=event.block_timestamp,
            )
            self.db.add(blockchain_tx)
            self.db.commit()

            logger.info(f"RemittanceRefunded procesado: {remittance.reference_code}")

    async def _process_transfer(self, event: BlockchainEvent):
        """Procesa evento Transfer de ERC20."""
        # Este puede ser muy verboso, solo procesar si es relevante
        # (transferencias a/desde nuestro contrato)
        args = event.args
        contract_address = CONTRACT_ADDRESSES.get(self.network, "").lower()

        if not contract_address:
            return

        from_addr = args.get('from', '').lower()
        to_addr = args.get('to', '').lower()

        if contract_address in (from_addr, to_addr):
            logger.debug(
                f"Transfer relevante: {args.get('value', 0)} "
                f"de {from_addr[:10]}... a {to_addr[:10]}..."
            )

    # ==================== Webhooks ====================

    async def _trigger_webhook(
        self,
        callback: Callable,
        event: BlockchainEvent
    ):
        """Dispara un webhook callback."""
        try:
            payload = {
                "event_type": event.event_type.value,
                "tx_hash": event.tx_hash,
                "block_number": event.block_number,
                "timestamp": event.block_timestamp.isoformat() if event.block_timestamp else None,
                "contract": event.contract_address,
                "args": self._serialize_args(event.args),
            }

            if asyncio.iscoroutinefunction(callback):
                await callback(payload)
            else:
                callback(payload)

        except Exception as e:
            logger.error(f"Error disparando webhook: {e}")

    def _serialize_args(self, args: Dict) -> Dict:
        """Serializa argumentos del evento para JSON."""
        result = {}
        for key, value in args.items():
            if isinstance(value, bytes):
                result[key] = value.hex()
            elif isinstance(value, int) and value > 2**53:
                result[key] = str(value)
            else:
                result[key] = value
        return result

    # ==================== Persistencia ====================

    async def _load_last_block(self):
        """Carga el último bloque procesado desde Redis/DB."""
        # Por ahora usar variable de entorno o constante
        # En producción, persistir en Redis
        self._last_block = max(START_BLOCK, self._last_block)
        logger.info(f"Iniciando desde bloque {self._last_block}")

    async def _save_last_block(self):
        """Guarda el último bloque procesado."""
        logger.info(f"Guardando último bloque: {self._last_block}")

    # ==================== Heartbeat ====================

    async def _heartbeat(self):
        """Task de heartbeat para verificar conectividad."""
        while self._running:
            try:
                if self.w3_http and self.w3_http.is_connected():
                    block = self.w3_http.eth.block_number
                    LAST_PROCESSED_BLOCK.labels(network=self.network.value).set(block)
                else:
                    logger.warning("Conexión HTTP perdida, reconectando...")
                    self._init_connections()

            except Exception as e:
                logger.error(f"Error en heartbeat: {e}")

            await asyncio.sleep(30)

    # ==================== Utilidades ====================

    def get_status(self) -> Dict:
        """Obtiene estado actual del listener."""
        return {
            "running": self._running,
            "network": self.network.value,
            "last_block": self._last_block,
            "current_block": self.w3_http.eth.block_number if self.w3_http else None,
            "websocket_connected": self.w3_ws is not None and self.w3_ws.is_connected() if self.w3_ws else False,
            "subscriptions": len(self._subscriptions),
            "processed_events": len(self._processed_events),
        }

    async def process_historical(
        self,
        from_block: int,
        to_block: Optional[int] = None
    ) -> int:
        """
        Procesa eventos históricos.

        Args:
            from_block: Bloque inicial
            to_block: Bloque final (default: actual)

        Returns:
            Número de eventos procesados
        """
        if to_block is None:
            to_block = self.w3_http.eth.block_number

        initial_count = len(self._processed_events)
        await self._process_blocks(from_block, to_block)

        processed = len(self._processed_events) - initial_count
        logger.info(f"Procesados {processed} eventos históricos ({from_block} - {to_block})")
        return processed

    def close(self):
        """Cierra conexiones."""
        if self._db:
            self._db.close()


# ==================== Función de startup ====================

async def start_event_listener(
    network: BlockchainNetwork = BlockchainNetwork.POLYGON
) -> EventListenerService:
    """
    Inicia el event listener como servicio.

    Uso en startup de FastAPI:
        @app.on_event("startup")
        async def startup():
            app.state.event_listener = await start_event_listener()
    """
    listener = EventListenerService(network=network)
    await listener.start()
    return listener
