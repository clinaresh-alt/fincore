"""
Servicio de Relayer para FinCore.

Sistema robusto de gestión de transacciones blockchain con:
- Cola de nonces con Redis (anti-colisiones)
- Gas Tank con fee fijo al usuario
- Lógica de resubmission automática
- Métricas de gas (Prometheus)
- Reintentos inteligentes con backoff exponencial

Este servicio actúa como intermediario entre la aplicación y la blockchain,
garantizando que las transacciones se procesen de forma ordenada y confiable.
"""
import os
import json
import time
import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

import redis
from web3 import Web3
from web3.exceptions import TransactionNotFound
from eth_account import Account
from eth_account.signers.local import LocalAccount

from prometheus_client import Counter, Histogram, Gauge, Info

from app.core.config import settings
from app.services.blockchain_service import (
    BlockchainService,
    TransactionResult,
    GasEstimate,
    NETWORK_CONFIGS,
)
from app.models.blockchain import BlockchainNetwork, TransactionStatus

logger = logging.getLogger(__name__)


# ============ Configuración ============

# Redis keys
REDIS_NONCE_KEY = "relayer:nonce:{network}:{address}"
REDIS_NONCE_LOCK = "relayer:nonce_lock:{network}:{address}"
REDIS_TX_QUEUE = "relayer:tx_queue:{network}"
REDIS_PENDING_TXS = "relayer:pending_txs:{network}"
REDIS_GAS_TANK_BALANCE = "relayer:gas_tank:{network}"

# Configuración de gas
DEFAULT_GAS_PRICE_MULTIPLIER = float(os.getenv("GAS_PRICE_MULTIPLIER", "1.1"))
MAX_GAS_PRICE_GWEI = int(os.getenv("MAX_GAS_PRICE_GWEI", "500"))
MIN_GAS_PRICE_GWEI = int(os.getenv("MIN_GAS_PRICE_GWEI", "1"))
GAS_BUMP_PERCENTAGE = float(os.getenv("GAS_BUMP_PERCENTAGE", "0.15"))  # 15% bump
RESUBMIT_AFTER_SECONDS = int(os.getenv("RESUBMIT_AFTER_SECONDS", "60"))
MAX_RESUBMISSIONS = int(os.getenv("MAX_RESUBMISSIONS", "3"))

# Fee fijo por tipo de operación (en USD)
FIXED_FEE_CONFIG = {
    "lock": Decimal("0.50"),      # $0.50 por lock
    "release": Decimal("0.50"),   # $0.50 por release
    "refund": Decimal("0.50"),    # $0.50 por refund
    "transfer": Decimal("0.25"),  # $0.25 por transfer
    "default": Decimal("1.00"),   # $1.00 default
}

# Nonce lock timeout
NONCE_LOCK_TIMEOUT = 30  # segundos


# ============ Prometheus Metrics ============

# Counters
TX_SUBMITTED = Counter(
    'relayer_transactions_submitted_total',
    'Total number of transactions submitted',
    ['network', 'operation', 'status']
)
TX_CONFIRMED = Counter(
    'relayer_transactions_confirmed_total',
    'Total number of transactions confirmed',
    ['network', 'operation']
)
TX_FAILED = Counter(
    'relayer_transactions_failed_total',
    'Total number of transactions failed',
    ['network', 'operation', 'reason']
)
TX_RESUBMITTED = Counter(
    'relayer_transactions_resubmitted_total',
    'Total number of transactions resubmitted with higher gas',
    ['network']
)
NONCE_COLLISIONS = Counter(
    'relayer_nonce_collisions_total',
    'Total number of nonce collisions detected',
    ['network']
)

# Histograms
TX_CONFIRMATION_TIME = Histogram(
    'relayer_transaction_confirmation_seconds',
    'Time to confirm transactions',
    ['network', 'operation'],
    buckets=[5, 10, 30, 60, 120, 300, 600]
)
GAS_USED = Histogram(
    'relayer_gas_used',
    'Gas used per transaction',
    ['network', 'operation'],
    buckets=[21000, 50000, 100000, 200000, 500000, 1000000]
)
GAS_PRICE = Histogram(
    'relayer_gas_price_gwei',
    'Gas price in Gwei',
    ['network'],
    buckets=[1, 5, 10, 25, 50, 100, 200, 500]
)

# Gauges
PENDING_TX_COUNT = Gauge(
    'relayer_pending_transactions',
    'Number of pending transactions',
    ['network']
)
GAS_TANK_BALANCE = Gauge(
    'relayer_gas_tank_balance',
    'Gas tank balance in native token',
    ['network']
)
CURRENT_NONCE = Gauge(
    'relayer_current_nonce',
    'Current nonce for operator address',
    ['network', 'address']
)


# ============ Data Classes ============

class TransactionPriority(str, Enum):
    """Prioridad de transacción."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class RelayerTransaction:
    """Transacción en cola del relayer."""
    id: str
    to: str
    data: str
    value: int = 0
    operation: str = "default"
    priority: TransactionPriority = TransactionPriority.NORMAL
    gas_limit: Optional[int] = None
    max_fee_gwei: Optional[Decimal] = None
    callback_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    # Estado de procesamiento
    tx_hash: Optional[str] = None
    nonce: Optional[int] = None
    submissions: int = 0
    last_submitted_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    status: str = "queued"  # queued, pending, confirmed, failed


@dataclass
class GasTankInfo:
    """Información del Gas Tank."""
    network: str
    balance_native: Decimal
    balance_usd: Decimal
    pending_cost_usd: Decimal
    available_usd: Decimal
    low_balance_alert: bool
    last_refilled_at: Optional[datetime]


@dataclass
class NonceInfo:
    """Información de nonce."""
    network: str
    address: str
    chain_nonce: int
    local_nonce: int
    pending_count: int
    last_synced_at: datetime


# ============ Excepciones ============

class RelayerError(Exception):
    """Error base del relayer."""
    pass


class NonceLockError(RelayerError):
    """Error al obtener lock de nonce."""
    pass


class GasEstimationError(RelayerError):
    """Error estimando gas."""
    pass


class TransactionSubmissionError(RelayerError):
    """Error enviando transacción."""
    pass


class InsufficientGasError(RelayerError):
    """Gas tank sin fondos suficientes."""
    pass


# ============ Servicio Principal ============

class RelayerService:
    """
    Servicio de Relayer para transacciones blockchain.

    Características:
    - Gestión de nonces con Redis (evita colisiones)
    - Cola de transacciones con prioridad
    - Gas Tank con fee fijo para usuarios
    - Resubmission automática con gas mayor
    - Métricas detalladas (Prometheus)
    """

    def __init__(
        self,
        network: BlockchainNetwork = BlockchainNetwork.POLYGON,
        private_key: Optional[str] = None,
        redis_url: Optional[str] = None,
    ):
        """
        Inicializa el relayer.

        Args:
            network: Red blockchain
            private_key: Clave privada del operador
            redis_url: URL de Redis (opcional)
        """
        self.network = network
        self.blockchain_service = BlockchainService(network=network, private_key=private_key)

        # Cuenta operadora
        self._private_key = private_key or os.getenv("BLOCKCHAIN_OPERATOR_KEY")
        self._operator: Optional[LocalAccount] = None
        if self._private_key:
            self._operator = Account.from_key(self._private_key)

        # Conexión Redis
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        self.redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True,
        )

        # Web3 directo para operaciones de bajo nivel
        self.w3 = self.blockchain_service.w3

        # Cache local de nonce
        self._local_nonce_cache: Dict[str, int] = {}

        logger.info(f"RelayerService inicializado para {network.value}")

    @property
    def operator_address(self) -> Optional[str]:
        """Dirección del operador."""
        return self._operator.address if self._operator else None

    # ==================== GESTIÓN DE NONCES ====================

    async def get_next_nonce(self, address: Optional[str] = None) -> int:
        """
        Obtiene el siguiente nonce disponible con lock distribuido.

        Args:
            address: Dirección (default: operador)

        Returns:
            Siguiente nonce disponible

        Raises:
            NonceLockError: Si no se puede obtener el lock
        """
        address = address or self.operator_address
        if not address:
            raise RelayerError("No hay dirección de operador configurada")

        lock_key = REDIS_NONCE_LOCK.format(network=self.network.value, address=address)
        nonce_key = REDIS_NONCE_KEY.format(network=self.network.value, address=address)

        # Intentar obtener lock con timeout
        lock_acquired = False
        for attempt in range(10):
            lock_acquired = self.redis.set(
                lock_key,
                "1",
                nx=True,
                ex=NONCE_LOCK_TIMEOUT
            )
            if lock_acquired:
                break
            await asyncio.sleep(0.1 * (attempt + 1))

        if not lock_acquired:
            NONCE_COLLISIONS.labels(network=self.network.value).inc()
            raise NonceLockError(f"No se pudo obtener lock de nonce para {address}")

        try:
            # Obtener nonce de chain
            chain_nonce = self.w3.eth.get_transaction_count(address, 'pending')

            # Obtener nonce local de Redis
            local_nonce_str = self.redis.get(nonce_key)
            local_nonce = int(local_nonce_str) if local_nonce_str else chain_nonce

            # Usar el mayor de los dos
            next_nonce = max(chain_nonce, local_nonce)

            # Incrementar y guardar
            self.redis.set(nonce_key, str(next_nonce + 1), ex=3600)

            # Actualizar métricas
            CURRENT_NONCE.labels(
                network=self.network.value,
                address=address
            ).set(next_nonce)

            logger.debug(f"Nonce asignado: {next_nonce} para {address}")
            return next_nonce

        finally:
            # Liberar lock
            self.redis.delete(lock_key)

    async def sync_nonce(self, address: Optional[str] = None) -> NonceInfo:
        """
        Sincroniza el nonce local con el de la blockchain.

        Args:
            address: Dirección a sincronizar

        Returns:
            NonceInfo con estado actual
        """
        address = address or self.operator_address
        if not address:
            raise RelayerError("No hay dirección de operador configurada")

        nonce_key = REDIS_NONCE_KEY.format(network=self.network.value, address=address)

        # Obtener nonce de chain
        chain_nonce = self.w3.eth.get_transaction_count(address, 'latest')
        pending_nonce = self.w3.eth.get_transaction_count(address, 'pending')

        # Actualizar en Redis
        self.redis.set(nonce_key, str(pending_nonce), ex=3600)

        return NonceInfo(
            network=self.network.value,
            address=address,
            chain_nonce=chain_nonce,
            local_nonce=pending_nonce,
            pending_count=pending_nonce - chain_nonce,
            last_synced_at=datetime.utcnow(),
        )

    # ==================== ESTIMACIÓN DE GAS ====================

    async def estimate_gas(
        self,
        to: str,
        data: str,
        value: int = 0,
        from_address: Optional[str] = None,
    ) -> GasEstimate:
        """
        Estima el gas necesario para una transacción.

        Args:
            to: Dirección destino
            data: Calldata
            value: Valor en wei
            from_address: Dirección origen

        Returns:
            GasEstimate con detalles

        Raises:
            GasEstimationError: Si falla la estimación
        """
        from_address = from_address or self.operator_address

        try:
            # Estimar gas limit
            gas_limit = self.w3.eth.estimate_gas({
                'from': from_address,
                'to': Web3.to_checksum_address(to),
                'data': data,
                'value': value,
            })

            # Agregar margen de seguridad (20%)
            gas_limit = int(gas_limit * 1.2)

            # Obtener precios de gas
            try:
                # EIP-1559
                fee_history = self.w3.eth.fee_history(5, 'latest', [25, 50, 75])
                base_fee = fee_history['baseFeePerGas'][-1]
                priority_fee = int(sum(fee_history['reward'][-1]) / 3)  # Promedio

                max_fee = int(base_fee * 2 + priority_fee)
                gas_price_gwei = Decimal(max_fee) / Decimal(10**9)
                priority_fee_gwei = Decimal(priority_fee) / Decimal(10**9)
            except Exception:
                # Legacy gas price
                gas_price = self.w3.eth.gas_price
                gas_price_gwei = Decimal(gas_price) / Decimal(10**9)
                max_fee = gas_price
                priority_fee_gwei = Decimal("0")

            # Aplicar multiplicador
            gas_price_gwei = gas_price_gwei * Decimal(str(DEFAULT_GAS_PRICE_MULTIPLIER))

            # Limitar precio máximo
            if gas_price_gwei > MAX_GAS_PRICE_GWEI:
                gas_price_gwei = Decimal(str(MAX_GAS_PRICE_GWEI))

            # Calcular costo estimado
            cost_wei = gas_limit * int(gas_price_gwei * 10**9)
            cost_native = Decimal(cost_wei) / Decimal(10**18)

            # Estimar costo en USD (usando precio aproximado)
            native_price_usd = self._get_native_token_price()
            cost_usd = cost_native * native_price_usd

            # Registrar métrica
            GAS_PRICE.labels(network=self.network.value).observe(float(gas_price_gwei))

            return GasEstimate(
                gas_limit=gas_limit,
                gas_price_gwei=gas_price_gwei,
                max_fee_gwei=Decimal(max_fee) / Decimal(10**9),
                priority_fee_gwei=priority_fee_gwei,
                estimated_cost_native=cost_native,
                estimated_cost_usd=cost_usd,
            )

        except Exception as e:
            logger.error(f"Error estimando gas: {e}")
            raise GasEstimationError(f"Error estimando gas: {e}")

    def _get_native_token_price(self) -> Decimal:
        """Obtiene precio del token nativo en USD (placeholder)."""
        # En producción, consultar oracle o API de precios
        prices = {
            BlockchainNetwork.POLYGON: Decimal("0.50"),
            BlockchainNetwork.POLYGON_AMOY: Decimal("0.50"),
            BlockchainNetwork.ETHEREUM: Decimal("2500"),
            BlockchainNetwork.ETHEREUM_SEPOLIA: Decimal("2500"),
            BlockchainNetwork.ARBITRUM: Decimal("2500"),
            BlockchainNetwork.BASE: Decimal("2500"),
        }
        return prices.get(self.network, Decimal("1"))

    # ==================== GAS TANK ====================

    async def get_gas_tank_info(self) -> GasTankInfo:
        """
        Obtiene información del Gas Tank.

        Returns:
            GasTankInfo con balance y estado
        """
        if not self.operator_address:
            raise RelayerError("No hay operador configurado")

        # Balance del operador
        balance_wei = self.w3.eth.get_balance(self.operator_address)
        balance_native = Decimal(balance_wei) / Decimal(10**18)

        # Precio en USD
        native_price = self._get_native_token_price()
        balance_usd = balance_native * native_price

        # Estimar costo de transacciones pendientes
        pending_key = REDIS_PENDING_TXS.format(network=self.network.value)
        pending_count = self.redis.llen(pending_key)
        avg_tx_cost_usd = Decimal("0.10")  # Costo promedio estimado
        pending_cost_usd = pending_count * avg_tx_cost_usd

        available_usd = balance_usd - pending_cost_usd

        # Alerta de bajo balance
        low_balance_threshold = Decimal("10.00")  # $10 USD
        low_balance_alert = available_usd < low_balance_threshold

        # Actualizar métricas
        GAS_TANK_BALANCE.labels(network=self.network.value).set(float(balance_native))

        return GasTankInfo(
            network=self.network.value,
            balance_native=balance_native,
            balance_usd=balance_usd,
            pending_cost_usd=pending_cost_usd,
            available_usd=available_usd,
            low_balance_alert=low_balance_alert,
            last_refilled_at=None,  # TODO: Implementar tracking
        )

    def get_fixed_fee(self, operation: str) -> Decimal:
        """
        Obtiene el fee fijo para una operación.

        Args:
            operation: Tipo de operación

        Returns:
            Fee en USD
        """
        return FIXED_FEE_CONFIG.get(operation, FIXED_FEE_CONFIG["default"])

    # ==================== ENVÍO DE TRANSACCIONES ====================

    async def submit_transaction(
        self,
        to: str,
        data: str,
        value: int = 0,
        operation: str = "default",
        priority: TransactionPriority = TransactionPriority.NORMAL,
        gas_limit: Optional[int] = None,
        max_fee_gwei: Optional[Decimal] = None,
        metadata: Optional[Dict] = None,
        wait_for_confirmation: bool = False,
        timeout: int = 300,
    ) -> TransactionResult:
        """
        Envía una transacción a la blockchain.

        Args:
            to: Dirección destino
            data: Calldata
            value: Valor en wei
            operation: Tipo de operación
            priority: Prioridad
            gas_limit: Límite de gas (auto si None)
            max_fee_gwei: Max fee (auto si None)
            metadata: Metadatos adicionales
            wait_for_confirmation: Esperar confirmación
            timeout: Timeout en segundos

        Returns:
            TransactionResult con hash y estado
        """
        if not self._operator:
            raise RelayerError("No hay operador configurado")

        start_time = time.time()
        tx_id = str(uuid4())

        try:
            # Verificar gas tank
            gas_info = await self.get_gas_tank_info()
            if gas_info.low_balance_alert:
                logger.warning(f"Gas tank bajo: {gas_info.available_usd} USD disponible")

            # Estimar gas si no se proporciona
            if gas_limit is None:
                estimate = await self.estimate_gas(to, data, value)
                gas_limit = estimate.gas_limit
                if max_fee_gwei is None:
                    max_fee_gwei = estimate.max_fee_gwei

            # Obtener nonce
            nonce = await self.get_next_nonce()

            # Construir transacción
            tx = self._build_transaction(
                to=to,
                data=data,
                value=value,
                nonce=nonce,
                gas_limit=gas_limit,
                max_fee_gwei=max_fee_gwei,
                priority=priority,
            )

            # Firmar
            signed_tx = self.w3.eth.account.sign_transaction(tx, self._private_key)

            # Enviar
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = tx_hash.hex()

            logger.info(f"Transacción enviada: {tx_hash_hex} (nonce={nonce}, op={operation})")

            # Registrar métricas
            TX_SUBMITTED.labels(
                network=self.network.value,
                operation=operation,
                status="submitted"
            ).inc()

            # Guardar en pending
            self._save_pending_transaction(
                tx_id=tx_id,
                tx_hash=tx_hash_hex,
                nonce=nonce,
                operation=operation,
                metadata=metadata or {},
            )

            # Actualizar gauge de pendientes
            pending_key = REDIS_PENDING_TXS.format(network=self.network.value)
            PENDING_TX_COUNT.labels(network=self.network.value).set(
                self.redis.llen(pending_key)
            )

            if wait_for_confirmation:
                return await self._wait_for_confirmation(
                    tx_hash_hex,
                    operation,
                    start_time,
                    timeout,
                )

            return TransactionResult(
                success=True,
                tx_hash=tx_hash_hex,
            )

        except Exception as e:
            logger.error(f"Error enviando transacción: {e}")
            TX_FAILED.labels(
                network=self.network.value,
                operation=operation,
                reason="submission_error"
            ).inc()
            return TransactionResult(
                success=False,
                error=str(e),
            )

    def _build_transaction(
        self,
        to: str,
        data: str,
        value: int,
        nonce: int,
        gas_limit: int,
        max_fee_gwei: Optional[Decimal],
        priority: TransactionPriority,
    ) -> Dict:
        """Construye el objeto de transacción."""
        # Ajustar gas según prioridad
        priority_multipliers = {
            TransactionPriority.LOW: Decimal("0.9"),
            TransactionPriority.NORMAL: Decimal("1.0"),
            TransactionPriority.HIGH: Decimal("1.3"),
            TransactionPriority.URGENT: Decimal("1.8"),
        }
        multiplier = priority_multipliers.get(priority, Decimal("1.0"))

        base_fee = int((max_fee_gwei or Decimal("30")) * multiplier * 10**9)
        priority_fee = int(base_fee * Decimal("0.1"))  # 10% del base fee

        return {
            'chainId': NETWORK_CONFIGS[self.network].chain_id,
            'from': self.operator_address,
            'to': Web3.to_checksum_address(to),
            'data': data,
            'value': value,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': base_fee,
            'maxPriorityFeePerGas': priority_fee,
        }

    def _save_pending_transaction(
        self,
        tx_id: str,
        tx_hash: str,
        nonce: int,
        operation: str,
        metadata: Dict,
    ):
        """Guarda transacción pendiente en Redis."""
        pending_key = REDIS_PENDING_TXS.format(network=self.network.value)
        tx_data = {
            'id': tx_id,
            'tx_hash': tx_hash,
            'nonce': nonce,
            'operation': operation,
            'metadata': metadata,
            'submitted_at': datetime.utcnow().isoformat(),
            'submissions': 1,
        }
        self.redis.rpush(pending_key, json.dumps(tx_data))
        self.redis.expire(pending_key, 86400)  # 24 horas

    async def _wait_for_confirmation(
        self,
        tx_hash: str,
        operation: str,
        start_time: float,
        timeout: int,
    ) -> TransactionResult:
        """Espera confirmación de transacción."""
        while time.time() - start_time < timeout:
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    elapsed = time.time() - start_time

                    # Registrar métricas
                    TX_CONFIRMATION_TIME.labels(
                        network=self.network.value,
                        operation=operation
                    ).observe(elapsed)

                    GAS_USED.labels(
                        network=self.network.value,
                        operation=operation
                    ).observe(receipt['gasUsed'])

                    if receipt['status'] == 1:
                        TX_CONFIRMED.labels(
                            network=self.network.value,
                            operation=operation
                        ).inc()

                        return TransactionResult(
                            success=True,
                            tx_hash=tx_hash,
                            block_number=receipt['blockNumber'],
                            gas_used=receipt['gasUsed'],
                        )
                    else:
                        TX_FAILED.labels(
                            network=self.network.value,
                            operation=operation,
                            reason="reverted"
                        ).inc()

                        return TransactionResult(
                            success=False,
                            tx_hash=tx_hash,
                            error="Transaction reverted",
                        )

            except TransactionNotFound:
                pass

            await asyncio.sleep(2)

        return TransactionResult(
            success=False,
            tx_hash=tx_hash,
            error="Timeout waiting for confirmation",
        )

    # ==================== RESUBMISSION ====================

    async def check_and_resubmit_stuck_transactions(self) -> int:
        """
        Verifica y re-envía transacciones atascadas.

        Returns:
            Número de transacciones re-enviadas
        """
        if not self._operator:
            return 0

        pending_key = REDIS_PENDING_TXS.format(network=self.network.value)
        pending_txs = self.redis.lrange(pending_key, 0, -1)
        resubmitted = 0

        for tx_json in pending_txs:
            try:
                tx_data = json.loads(tx_json)
                submitted_at = datetime.fromisoformat(tx_data['submitted_at'])
                age_seconds = (datetime.utcnow() - submitted_at).total_seconds()

                # Si es muy vieja y aún pendiente
                if age_seconds > RESUBMIT_AFTER_SECONDS:
                    # Verificar si ya se confirmó
                    try:
                        receipt = self.w3.eth.get_transaction_receipt(tx_data['tx_hash'])
                        if receipt:
                            # Ya confirmada, remover de pendientes
                            self.redis.lrem(pending_key, 1, tx_json)
                            continue
                    except TransactionNotFound:
                        pass

                    # Verificar límite de resubmissions
                    if tx_data.get('submissions', 1) >= MAX_RESUBMISSIONS:
                        logger.warning(
                            f"Transacción {tx_data['tx_hash']} alcanzó máximo de resubmissions"
                        )
                        continue

                    # Re-enviar con gas más alto
                    success = await self._resubmit_transaction(tx_data)
                    if success:
                        resubmitted += 1
                        TX_RESUBMITTED.labels(network=self.network.value).inc()

            except Exception as e:
                logger.error(f"Error procesando tx pendiente: {e}")

        return resubmitted

    async def _resubmit_transaction(self, tx_data: Dict) -> bool:
        """Re-envía una transacción con gas más alto."""
        try:
            old_tx = self.w3.eth.get_transaction(tx_data['tx_hash'])

            # Calcular nuevo gas price (bump)
            old_max_fee = old_tx.get('maxFeePerGas', old_tx.get('gasPrice', 0))
            new_max_fee = int(old_max_fee * (1 + GAS_BUMP_PERCENTAGE))
            new_priority_fee = int(new_max_fee * 0.1)

            # Construir nueva transacción con mismo nonce
            new_tx = {
                'chainId': NETWORK_CONFIGS[self.network].chain_id,
                'from': self.operator_address,
                'to': old_tx['to'],
                'data': old_tx['input'],
                'value': old_tx['value'],
                'nonce': old_tx['nonce'],
                'gas': old_tx['gas'],
                'maxFeePerGas': new_max_fee,
                'maxPriorityFeePerGas': new_priority_fee,
            }

            # Firmar y enviar
            signed_tx = self.w3.eth.account.sign_transaction(new_tx, self._private_key)
            new_tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            logger.info(
                f"Transacción re-enviada: {tx_data['tx_hash']} -> {new_tx_hash.hex()} "
                f"(gas bump: {old_max_fee} -> {new_max_fee})"
            )

            # Actualizar en Redis
            pending_key = REDIS_PENDING_TXS.format(network=self.network.value)
            tx_data['tx_hash'] = new_tx_hash.hex()
            tx_data['submissions'] = tx_data.get('submissions', 1) + 1
            tx_data['submitted_at'] = datetime.utcnow().isoformat()

            # Remover viejo y agregar nuevo
            self.redis.lrem(pending_key, 1, json.dumps(tx_data))
            self.redis.rpush(pending_key, json.dumps(tx_data))

            return True

        except Exception as e:
            logger.error(f"Error re-enviando transacción: {e}")
            return False

    # ==================== HELPERS ====================

    async def get_pending_transactions(self) -> List[Dict]:
        """Obtiene lista de transacciones pendientes."""
        pending_key = REDIS_PENDING_TXS.format(network=self.network.value)
        pending_txs = self.redis.lrange(pending_key, 0, -1)
        return [json.loads(tx) for tx in pending_txs]

    async def get_transaction_status(self, tx_hash: str) -> Dict:
        """Obtiene estado de una transacción."""
        try:
            tx = self.w3.eth.get_transaction(tx_hash)
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                # Manejar caso donde receipt es None (transacción pendiente)
                if receipt is None:
                    return {
                        'tx_hash': tx_hash,
                        'status': 'pending',
                        'nonce': tx['nonce'],
                        'gas_price': tx.get('gasPrice', tx.get('maxFeePerGas')),
                    }
                return {
                    'tx_hash': tx_hash,
                    'status': 'confirmed' if receipt['status'] == 1 else 'failed',
                    'block_number': receipt['blockNumber'],
                    'gas_used': receipt['gasUsed'],
                    'confirmations': self.w3.eth.block_number - receipt['blockNumber'],
                }
            except TransactionNotFound:
                return {
                    'tx_hash': tx_hash,
                    'status': 'pending',
                    'nonce': tx['nonce'],
                    'gas_price': tx.get('gasPrice', tx.get('maxFeePerGas')),
                }
        except TransactionNotFound:
            return {
                'tx_hash': tx_hash,
                'status': 'not_found',
            }

    def close(self):
        """Cierra conexiones."""
        self.redis.close()


# ============ Factory Function ============

def get_relayer_service(
    network: BlockchainNetwork = BlockchainNetwork.POLYGON,
) -> RelayerService:
    """Factory para obtener instancia del relayer."""
    return RelayerService(network=network)
