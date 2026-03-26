"""
Tests para el Servicio de Relayer.

Tests unitarios y de estrés para:
- Sistema de colas de nonces (Redis)
- Gas Tank con fee fijo
- Lógica de resubmission
- Métricas de Prometheus
- Manejo de transacciones concurrentes
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4
import json

from app.services.relayer_service import (
    RelayerService,
    RelayerTransaction,
    TransactionPriority,
    GasTankInfo,
    NonceInfo,
    NonceLockError,
    GasEstimationError,
    InsufficientGasError,
    FIXED_FEE_CONFIG,
)
from app.services.blockchain_service import TransactionResult, GasEstimate
from app.models.blockchain import BlockchainNetwork


# ==================== FIXTURES ====================

@pytest.fixture
def mock_redis():
    """Mock de Redis."""
    redis_mock = MagicMock()
    redis_mock.set = MagicMock(return_value=True)
    redis_mock.get = MagicMock(return_value="10")
    redis_mock.delete = MagicMock()
    redis_mock.rpush = MagicMock()
    redis_mock.lrange = MagicMock(return_value=[])
    redis_mock.llen = MagicMock(return_value=0)
    redis_mock.lrem = MagicMock()
    redis_mock.expire = MagicMock()
    redis_mock.close = MagicMock()
    return redis_mock


@pytest.fixture
def mock_web3():
    """Mock de Web3."""
    w3_mock = MagicMock()
    w3_mock.is_connected.return_value = True
    w3_mock.eth.get_transaction_count.return_value = 10
    w3_mock.eth.get_balance.return_value = 5 * 10**18  # 5 ETH/MATIC
    w3_mock.eth.gas_price = 30 * 10**9  # 30 Gwei
    w3_mock.eth.estimate_gas.return_value = 100000
    w3_mock.eth.fee_history.return_value = {
        'baseFeePerGas': [30 * 10**9],
        'reward': [[2 * 10**9, 3 * 10**9, 4 * 10**9]],
    }
    w3_mock.eth.block_number = 1000000
    w3_mock.eth.send_raw_transaction.return_value = bytes.fromhex('a' * 64)
    w3_mock.eth.account.sign_transaction.return_value = MagicMock(
        raw_transaction=b'signed_tx_data'
    )
    w3_mock.eth.get_transaction_receipt.return_value = None
    w3_mock.eth.get_transaction.side_effect = Exception("Not found")
    return w3_mock


@pytest.fixture
def mock_blockchain_service():
    """Mock del BlockchainService."""
    service = MagicMock()
    service.w3 = MagicMock()
    service.network = BlockchainNetwork.POLYGON
    return service


@pytest.fixture
def relayer_service(mock_redis, mock_web3, mock_blockchain_service):
    """Instancia del RelayerService con mocks."""
    with patch('app.services.relayer_service.redis.Redis', return_value=mock_redis):
        with patch('app.services.relayer_service.BlockchainService', return_value=mock_blockchain_service):
            with patch('app.services.relayer_service.Account.from_key') as mock_account:
                mock_account.return_value = MagicMock(
                    address='0x1234567890123456789012345678901234567890'
                )
                service = RelayerService(
                    network=BlockchainNetwork.POLYGON,
                    private_key='0x' + 'a' * 64,
                )
                service.w3 = mock_web3
                service.redis = mock_redis
                return service


# ==================== TESTS DE NONCES ====================

class TestNonceManagement:
    """Tests del sistema de gestión de nonces."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_next_nonce_success(self, relayer_service, mock_redis, mock_web3):
        """Test obtener siguiente nonce exitosamente."""
        mock_redis.set.return_value = True
        mock_web3.eth.get_transaction_count.return_value = 10

        nonce = await relayer_service.get_next_nonce()

        assert nonce == 10
        mock_redis.delete.assert_called()  # Lock liberado

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_next_nonce_lock_contention(self, relayer_service, mock_redis, mock_web3):
        """Test contención de lock de nonce."""
        # Simular que el lock ya está tomado las primeras veces
        # Usar return_value para evitar StopIteration
        lock_results = [False, False, False, True, True, True]
        call_count = [0]

        def mock_set(*args, **kwargs):
            if call_count[0] < len(lock_results):
                result = lock_results[call_count[0]]
                call_count[0] += 1
                return result
            return True

        mock_redis.set.side_effect = mock_set
        mock_web3.eth.get_transaction_count.return_value = 15

        nonce = await relayer_service.get_next_nonce()

        assert nonce == 15
        assert call_count[0] >= 4

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_next_nonce_uses_higher(self, relayer_service, mock_redis, mock_web3):
        """Test que usa el nonce mayor entre chain y local."""
        mock_redis.set.return_value = True
        mock_web3.eth.get_transaction_count.return_value = 10
        mock_redis.get.return_value = "15"  # Local más alto

        nonce = await relayer_service.get_next_nonce()

        assert nonce == 15

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sync_nonce(self, relayer_service, mock_redis, mock_web3):
        """Test sincronización de nonce."""
        mock_web3.eth.get_transaction_count.side_effect = [10, 12]  # latest, pending

        result = await relayer_service.sync_nonce()

        assert isinstance(result, NonceInfo)
        assert result.chain_nonce == 10
        assert result.local_nonce == 12
        assert result.pending_count == 2


# ==================== TESTS DE GAS ====================

class TestGasEstimation:
    """Tests de estimación de gas."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_estimate_gas_success(self, relayer_service, mock_web3):
        """Test estimación de gas exitosa."""
        mock_web3.eth.estimate_gas.return_value = 100000
        mock_web3.eth.fee_history.return_value = {
            'baseFeePerGas': [30 * 10**9],
            'reward': [[2 * 10**9, 3 * 10**9, 4 * 10**9]],
        }

        estimate = await relayer_service.estimate_gas(
            to='0x' + '1' * 40,
            data='0x',
            value=0,
        )

        assert isinstance(estimate, GasEstimate)
        assert estimate.gas_limit == 120000  # 100000 * 1.2
        assert estimate.gas_price_gwei > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_estimate_gas_with_margin(self, relayer_service, mock_web3):
        """Test que el gas tiene margen de seguridad."""
        mock_web3.eth.estimate_gas.return_value = 50000

        estimate = await relayer_service.estimate_gas(
            to='0x' + '1' * 40,
            data='0x',
        )

        # Debe ser 20% mayor
        assert estimate.gas_limit == 60000

    @pytest.mark.integration
    def test_get_fixed_fee(self, relayer_service):
        """Test obtener fee fijo por operación."""
        assert relayer_service.get_fixed_fee("lock") == Decimal("0.50")
        assert relayer_service.get_fixed_fee("release") == Decimal("0.50")
        assert relayer_service.get_fixed_fee("transfer") == Decimal("0.25")
        assert relayer_service.get_fixed_fee("unknown") == Decimal("1.00")


# ==================== TESTS DE GAS TANK ====================

class TestGasTank:
    """Tests del Gas Tank."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_gas_tank_info(self, relayer_service, mock_web3, mock_redis):
        """Test obtener info del gas tank."""
        mock_web3.eth.get_balance.return_value = 100 * 10**18  # 100 MATIC (~$50 USD)
        mock_redis.llen.return_value = 5  # 5 transacciones pendientes

        info = await relayer_service.get_gas_tank_info()

        assert isinstance(info, GasTankInfo)
        assert info.balance_native == Decimal("100")
        # Con 100 MATIC a $0.50 = $50 USD disponible, no debería haber alerta
        assert info.low_balance_alert is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_gas_tank_low_balance_alert(self, relayer_service, mock_web3, mock_redis):
        """Test alerta de bajo balance."""
        mock_web3.eth.get_balance.return_value = int(0.01 * 10**18)  # 0.01 MATIC
        mock_redis.llen.return_value = 0

        info = await relayer_service.get_gas_tank_info()

        assert info.low_balance_alert is True


# ==================== TESTS DE TRANSACCIONES ====================

class TestTransactionSubmission:
    """Tests de envío de transacciones."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_submit_transaction_success(self, relayer_service, mock_web3, mock_redis):
        """Test envío de transacción exitoso."""
        mock_redis.set.return_value = True
        mock_web3.eth.get_transaction_count.return_value = 10
        mock_web3.eth.estimate_gas.return_value = 100000
        mock_web3.eth.send_raw_transaction.return_value = bytes.fromhex('ab' * 32)

        result = await relayer_service.submit_transaction(
            to='0x' + '1' * 40,
            data='0x12345678',
            operation='lock',
            wait_for_confirmation=False,
        )

        assert result.success is True
        assert result.tx_hash is not None
        mock_redis.rpush.assert_called()  # Guardado en pendientes

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_submit_transaction_with_priority(self, relayer_service, mock_web3, mock_redis):
        """Test envío con prioridad."""
        mock_redis.set.return_value = True
        mock_web3.eth.get_transaction_count.return_value = 10
        mock_web3.eth.estimate_gas.return_value = 100000

        result = await relayer_service.submit_transaction(
            to='0x' + '1' * 40,
            data='0x',
            priority=TransactionPriority.URGENT,
        )

        assert result.success is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_submit_transaction_wait_for_confirmation(
        self, relayer_service, mock_web3, mock_redis
    ):
        """Test esperar confirmación."""
        mock_redis.set.return_value = True
        mock_web3.eth.get_transaction_count.return_value = 10
        mock_web3.eth.estimate_gas.return_value = 100000

        # Simular confirmación después de un intento
        mock_web3.eth.get_transaction_receipt.side_effect = [
            None,  # Primera verificación
            {'status': 1, 'blockNumber': 1000000, 'gasUsed': 80000},  # Confirmado
        ]

        result = await relayer_service.submit_transaction(
            to='0x' + '1' * 40,
            data='0x',
            wait_for_confirmation=True,
            timeout=10,
        )

        assert result.success is True
        assert result.block_number == 1000000


# ==================== TESTS DE RESUBMISSION ====================

class TestResubmission:
    """Tests de re-envío de transacciones."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_check_no_stuck_transactions(self, relayer_service, mock_redis):
        """Test cuando no hay transacciones atascadas."""
        mock_redis.lrange.return_value = []

        count = await relayer_service.check_and_resubmit_stuck_transactions()

        assert count == 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_resubmit_stuck_transaction(self, relayer_service, mock_redis, mock_web3):
        """Test re-envío de transacción atascada."""
        old_time = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
        pending_tx = json.dumps({
            'id': str(uuid4()),
            'tx_hash': '0x' + 'a' * 64,
            'nonce': 10,
            'operation': 'lock',
            'metadata': {},
            'submitted_at': old_time,
            'submissions': 1,
        })

        mock_redis.lrange.return_value = [pending_tx]
        # Limpiar side_effect del fixture para configurar nuevos comportamientos
        mock_web3.eth.get_transaction.side_effect = None
        mock_web3.eth.get_transaction_receipt.side_effect = None
        mock_web3.eth.get_transaction_receipt.return_value = None  # No confirmada aún
        mock_web3.eth.get_transaction.return_value = {
            'to': '0x' + '1' * 40,
            'input': '0x12345678',
            'value': 0,
            'nonce': 10,
            'gas': 100000,
            'maxFeePerGas': 30 * 10**9,
        }

        with patch.object(relayer_service, '_resubmit_transaction', new_callable=AsyncMock) as mock_resubmit:
            mock_resubmit.return_value = True

            count = await relayer_service.check_and_resubmit_stuck_transactions()

            assert count == 1
            mock_resubmit.assert_called_once()


# ==================== TESTS DE HELPERS ====================

class TestHelpers:
    """Tests de funciones auxiliares."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_pending_transactions(self, relayer_service, mock_redis):
        """Test obtener transacciones pendientes."""
        mock_redis.lrange.return_value = [
            json.dumps({'id': '1', 'tx_hash': '0xabc'}),
            json.dumps({'id': '2', 'tx_hash': '0xdef'}),
        ]

        pending = await relayer_service.get_pending_transactions()

        assert len(pending) == 2
        assert pending[0]['id'] == '1'

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_transaction_status_confirmed(self, relayer_service, mock_web3):
        """Test estado de transacción confirmada."""
        # Limpiar side_effect del fixture para que return_value funcione
        mock_web3.eth.get_transaction.side_effect = None
        mock_web3.eth.get_transaction_receipt.side_effect = None

        mock_web3.eth.get_transaction.return_value = {'nonce': 10}
        mock_web3.eth.get_transaction_receipt.return_value = {
            'status': 1,
            'blockNumber': 999000,
            'gasUsed': 80000,
        }
        mock_web3.eth.block_number = 1000000

        status = await relayer_service.get_transaction_status('0x' + 'a' * 64)

        assert status['status'] == 'confirmed'
        assert status['confirmations'] == 1000

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_transaction_status_pending(self, relayer_service, mock_web3):
        """Test estado de transacción pendiente."""
        # Limpiar side_effect del fixture para que return_value funcione
        mock_web3.eth.get_transaction.side_effect = None
        mock_web3.eth.get_transaction_receipt.side_effect = None

        mock_web3.eth.get_transaction.return_value = {
            'nonce': 10,
            'gasPrice': 30 * 10**9,
        }
        # Retornar None indica que la TX existe pero no tiene receipt (pendiente)
        mock_web3.eth.get_transaction_receipt.return_value = None

        status = await relayer_service.get_transaction_status('0x' + 'a' * 64)

        assert status['status'] == 'pending'


# ==================== TESTS DE ESTRÉS ====================

class TestStress:
    """Tests de estrés para el sistema de nonces."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_nonce_requests(self, relayer_service, mock_redis, mock_web3):
        """Test solicitudes de nonce concurrentes."""
        mock_redis.set.return_value = True
        nonce_counter = [10]

        def increment_nonce(*args, **kwargs):
            result = nonce_counter[0]
            nonce_counter[0] += 1
            return result

        mock_web3.eth.get_transaction_count.return_value = 10
        mock_redis.get.side_effect = lambda key: str(increment_nonce())

        # Ejecutar 10 solicitudes concurrentes
        tasks = [relayer_service.get_next_nonce() for _ in range(10)]
        nonces = await asyncio.gather(*tasks, return_exceptions=True)

        # Verificar que no hubo errores graves
        successful = [n for n in nonces if isinstance(n, int)]
        assert len(successful) >= 5  # Al menos 50% exitosos

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_high_volume_transaction_queue(self, relayer_service, mock_redis, mock_web3):
        """Test cola de transacciones de alto volumen."""
        mock_redis.set.return_value = True
        mock_web3.eth.get_transaction_count.return_value = 10
        mock_web3.eth.estimate_gas.return_value = 100000
        mock_web3.eth.send_raw_transaction.return_value = bytes.fromhex('ab' * 32)

        # Enviar 20 transacciones
        tasks = []
        for i in range(20):
            tasks.append(
                relayer_service.submit_transaction(
                    to='0x' + '1' * 40,
                    data=f'0x{i:08x}',
                    operation='transfer',
                    wait_for_confirmation=False,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verificar que la mayoría fueron exitosas
        successful = [r for r in results if isinstance(r, TransactionResult) and r.success]
        assert len(successful) >= 15  # Al menos 75% exitosos

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_nonce_recovery_after_failure(self, relayer_service, mock_redis, mock_web3):
        """Test recuperación de nonce después de fallo."""
        mock_redis.set.return_value = True

        # Primer intento falla
        mock_web3.eth.get_transaction_count.side_effect = [
            Exception("RPC error"),
            10,  # Segundo intento exitoso
        ]

        # Primera llamada debería fallar
        with pytest.raises(Exception):
            await relayer_service.get_next_nonce()

        # Restaurar el mock
        mock_web3.eth.get_transaction_count.side_effect = None
        mock_web3.eth.get_transaction_count.return_value = 10

        # Segunda llamada debería funcionar
        nonce = await relayer_service.get_next_nonce()
        assert nonce == 10


# ==================== TESTS DE MÉTRICAS ====================

class TestMetrics:
    """Tests de métricas Prometheus."""

    @pytest.mark.integration
    def test_metrics_defined(self):
        """Test que las métricas están definidas."""
        from app.services.relayer_service import (
            TX_SUBMITTED,
            TX_CONFIRMED,
            TX_FAILED,
            TX_RESUBMITTED,
            NONCE_COLLISIONS,
            TX_CONFIRMATION_TIME,
            GAS_USED,
            GAS_PRICE,
            PENDING_TX_COUNT,
            GAS_TANK_BALANCE,
            CURRENT_NONCE,
        )

        # Verificar que son objetos de métricas válidos
        assert TX_SUBMITTED is not None
        assert TX_CONFIRMED is not None
        assert TX_FAILED is not None
        assert TX_RESUBMITTED is not None
        assert NONCE_COLLISIONS is not None
        assert TX_CONFIRMATION_TIME is not None
        assert GAS_USED is not None
        assert GAS_PRICE is not None
        assert PENDING_TX_COUNT is not None
        assert GAS_TANK_BALANCE is not None
        assert CURRENT_NONCE is not None


# ==================== TESTS DE PRIORIDADES ====================

class TestTransactionPriorities:
    """Tests del sistema de prioridades."""

    @pytest.mark.integration
    def test_priority_values(self):
        """Test valores de prioridad."""
        assert TransactionPriority.LOW.value == "low"
        assert TransactionPriority.NORMAL.value == "normal"
        assert TransactionPriority.HIGH.value == "high"
        assert TransactionPriority.URGENT.value == "urgent"

    @pytest.mark.integration
    def test_fee_config_values(self):
        """Test configuración de fees."""
        assert FIXED_FEE_CONFIG["lock"] == Decimal("0.50")
        assert FIXED_FEE_CONFIG["release"] == Decimal("0.50")
        assert FIXED_FEE_CONFIG["refund"] == Decimal("0.50")
        assert FIXED_FEE_CONFIG["transfer"] == Decimal("0.25")
        assert FIXED_FEE_CONFIG["default"] == Decimal("1.00")
