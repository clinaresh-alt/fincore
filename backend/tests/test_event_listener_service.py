"""
Tests para el Event Listener Service.

Tests unitarios para:
- Conexión a blockchain
- Procesamiento de eventos
- Suscripciones y callbacks
- Manejo de errores
- Métricas
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from uuid import uuid4
from decimal import Decimal

from app.services.event_listener_service import (
    EventListenerService,
    BlockchainEvent,
    EventType,
    EventSubscription,
    ConnectionError,
    ProcessingError,
    EVENTS_RECEIVED,
    EVENTS_PROCESSED,
)
from app.models.blockchain import BlockchainNetwork
from app.models.remittance import RemittanceStatus


# ==================== FIXTURES ====================

@pytest.fixture
def mock_web3():
    """Mock de Web3."""
    w3 = MagicMock()
    w3.is_connected.return_value = True
    w3.eth.block_number = 1000000
    w3.eth.get_block.return_value = {
        'timestamp': int(datetime.utcnow().timestamp()),
        'number': 1000000,
    }
    w3.eth.get_transaction_receipt.return_value = {
        'status': 1,
        'blockNumber': 1000000,
    }
    return w3


@pytest.fixture
def mock_contract():
    """Mock de contrato."""
    contract = MagicMock()

    # Mock de eventos
    mock_filter = MagicMock()
    mock_filter.get_all_entries.return_value = []

    contract.events.RemittanceCreated.create_filter.return_value = mock_filter
    contract.events.RemittanceReleased.create_filter.return_value = mock_filter
    contract.events.RemittanceRefunded.create_filter.return_value = mock_filter

    return contract


@pytest.fixture
def mock_db():
    """Mock de sesión de base de datos."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.add = MagicMock()
    db.commit = MagicMock()
    return db


@pytest.fixture
def event_listener(mock_web3, mock_contract, mock_db):
    """Instancia del EventListenerService con mocks."""
    with patch('app.services.event_listener_service.Web3') as MockWeb3:
        MockWeb3.return_value = mock_web3
        MockWeb3.HTTPProvider = MagicMock()
        MockWeb3.WebsocketProvider = MagicMock()
        MockWeb3.to_checksum_address = lambda x: x

        with patch('app.services.event_listener_service.SessionLocal', return_value=mock_db):
            listener = EventListenerService(
                network=BlockchainNetwork.POLYGON,
                use_websocket=False,
            )
            listener.w3_http = mock_web3
            listener.remittance_contract = mock_contract
            listener._db = mock_db
            return listener


@pytest.fixture
def sample_log():
    """Log de evento de prueba."""
    return {
        'transactionHash': bytes.fromhex('a' * 64),
        'logIndex': 0,
        'blockNumber': 1000000,
        'address': '0x' + '1' * 40,
        'args': {
            'remittanceId': 1,
            'referenceId': bytes.fromhex('b' * 64),
            'sender': '0x' + '2' * 40,
            'token': '0x' + '3' * 40,
            'amount': 1000 * 10**6,  # 1000 USDC
            'fee': 10 * 10**6,  # 10 USDC
            'expiresAt': int((datetime.utcnow() + timedelta(hours=48)).timestamp()),
        },
    }


# ==================== TESTS DE CONEXIÓN ====================

class TestConnection:
    """Tests de conexión a blockchain."""

    @pytest.mark.integration
    def test_init_success(self, event_listener):
        """Test inicialización exitosa."""
        assert event_listener.network == BlockchainNetwork.POLYGON
        assert event_listener._running is False

    @pytest.mark.integration
    def test_get_status(self, event_listener):
        """Test obtener estado del listener."""
        status = event_listener.get_status()

        assert 'running' in status
        assert 'network' in status
        assert 'last_block' in status
        assert status['running'] is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_start_stop(self, event_listener):
        """Test iniciar y detener listener."""
        await event_listener.start()
        assert event_listener._running is True

        await event_listener.stop()
        assert event_listener._running is False


# ==================== TESTS DE SUSCRIPCIONES ====================

class TestSubscriptions:
    """Tests de suscripciones a eventos."""

    @pytest.mark.integration
    def test_subscribe(self, event_listener):
        """Test suscribir a evento."""
        callback = MagicMock()

        event_listener.subscribe(
            EventType.REMITTANCE_CREATED,
            callback,
        )

        assert len(event_listener._subscriptions) == 1
        assert event_listener._subscriptions[0].event_type == EventType.REMITTANCE_CREATED

    @pytest.mark.integration
    def test_subscribe_multiple(self, event_listener):
        """Test múltiples suscripciones."""
        callback1 = MagicMock()
        callback2 = MagicMock()

        event_listener.subscribe(EventType.REMITTANCE_CREATED, callback1)
        event_listener.subscribe(EventType.REMITTANCE_RELEASED, callback2)

        assert len(event_listener._subscriptions) == 2

    @pytest.mark.integration
    def test_register_webhook(self, event_listener):
        """Test registrar callback de webhook."""
        callback = MagicMock()
        event_listener.register_webhook(callback)

        assert len(event_listener._webhook_callbacks) == 1


# ==================== TESTS DE PROCESAMIENTO ====================

class TestEventProcessing:
    """Tests de procesamiento de eventos."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handle_remittance_created(self, event_listener, sample_log, mock_db):
        """Test procesar evento RemittanceCreated."""
        # Crear una remesa mock en la DB
        mock_remittance = MagicMock()
        mock_remittance.id = uuid4()
        mock_remittance.reference_code = 'b' * 20
        mock_remittance.status = RemittanceStatus.INITIATED
        mock_db.query.return_value.filter.return_value.first.return_value = mock_remittance

        # Procesar evento
        await event_listener._handle_event(EventType.REMITTANCE_CREATED, sample_log)

        # Verificar que se actualizó la remesa
        assert mock_remittance.status == RemittanceStatus.LOCKED

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handle_remittance_released(self, event_listener, sample_log, mock_db):
        """Test procesar evento RemittanceReleased."""
        mock_remittance = MagicMock()
        mock_remittance.id = uuid4()
        mock_remittance.reference_code = 'b' * 20
        mock_remittance.status = RemittanceStatus.LOCKED
        mock_db.query.return_value.filter.return_value.first.return_value = mock_remittance

        # Modificar log para Released
        sample_log['args'] = {
            'remittanceId': 1,
            'referenceId': bytes.fromhex('b' * 64),
            'operator': '0x' + '4' * 40,
            'amount': 1000 * 10**6,
        }

        await event_listener._handle_event(EventType.REMITTANCE_RELEASED, sample_log)

        assert mock_remittance.status == RemittanceStatus.COMPLETED

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_handle_remittance_refunded(self, event_listener, sample_log, mock_db):
        """Test procesar evento RemittanceRefunded."""
        mock_remittance = MagicMock()
        mock_remittance.id = uuid4()
        mock_remittance.reference_code = 'b' * 20
        mock_remittance.status = RemittanceStatus.LOCKED
        mock_db.query.return_value.filter.return_value.first.return_value = mock_remittance

        # Modificar log para Refunded
        sample_log['args'] = {
            'remittanceId': 1,
            'referenceId': bytes.fromhex('b' * 64),
            'sender': '0x' + '2' * 40,
            'amount': 1000 * 10**6,
        }

        await event_listener._handle_event(EventType.REMITTANCE_REFUNDED, sample_log)

        assert mock_remittance.status == RemittanceStatus.REFUNDED

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_idempotency(self, event_listener, sample_log, mock_db):
        """Test idempotencia - evento duplicado."""
        # Procesar evento primera vez
        await event_listener._handle_event(EventType.REMITTANCE_CREATED, sample_log)

        # Procesar mismo evento segunda vez
        await event_listener._handle_event(EventType.REMITTANCE_CREATED, sample_log)

        # Solo debería haberse añadido una vez al set de procesados
        event_id = f"{sample_log['transactionHash'].hex()}_{sample_log['logIndex']}"
        assert event_id in event_listener._processed_events


# ==================== TESTS DE CALLBACKS ====================

class TestCallbacks:
    """Tests de callbacks de eventos."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_callback_sync(self, event_listener, sample_log, mock_db):
        """Test callback síncrono."""
        callback = MagicMock()
        event_listener.subscribe(EventType.REMITTANCE_CREATED, callback)

        await event_listener._handle_event(EventType.REMITTANCE_CREATED, sample_log)

        callback.assert_called_once()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_callback_async(self, event_listener, sample_log, mock_db):
        """Test callback asíncrono."""
        callback = AsyncMock()
        event_listener.subscribe(EventType.REMITTANCE_CREATED, callback)

        await event_listener._handle_event(EventType.REMITTANCE_CREATED, sample_log)

        callback.assert_called_once()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_webhook_callback(self, event_listener, sample_log, mock_db):
        """Test callback de webhook."""
        webhook_callback = AsyncMock()
        event_listener.register_webhook(webhook_callback)

        await event_listener._handle_event(EventType.REMITTANCE_CREATED, sample_log)

        webhook_callback.assert_called_once()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_callback_error_handling(self, event_listener, sample_log, mock_db):
        """Test manejo de errores en callbacks."""
        callback = MagicMock(side_effect=Exception("Callback error"))
        event_listener.subscribe(EventType.REMITTANCE_CREATED, callback)

        # No debe propagar la excepción
        await event_listener._handle_event(EventType.REMITTANCE_CREATED, sample_log)

        callback.assert_called_once()


# ==================== TESTS DE POLLING ====================

class TestPolling:
    """Tests de polling de eventos."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_process_block_range(self, event_listener, mock_contract):
        """Test procesar rango de bloques."""
        mock_filter = MagicMock()
        mock_filter.get_all_entries.return_value = []
        mock_contract.events.RemittanceCreated.create_filter.return_value = mock_filter
        mock_contract.events.RemittanceReleased.create_filter.return_value = mock_filter
        mock_contract.events.RemittanceRefunded.create_filter.return_value = mock_filter

        await event_listener._process_block_range(1000, 1010)

        # Verificar que se crearon los filtros
        mock_contract.events.RemittanceCreated.create_filter.assert_called()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_process_historical(self, event_listener, mock_web3, mock_contract):
        """Test procesar eventos históricos."""
        mock_filter = MagicMock()
        mock_filter.get_all_entries.return_value = []
        mock_contract.events.RemittanceCreated.create_filter.return_value = mock_filter
        mock_contract.events.RemittanceReleased.create_filter.return_value = mock_filter
        mock_contract.events.RemittanceRefunded.create_filter.return_value = mock_filter

        processed = await event_listener.process_historical(
            from_block=1000,
            to_block=2000,
        )

        assert processed == 0  # No hay eventos en los mocks


# ==================== TESTS DE SERIALIZACIÓN ====================

class TestSerialization:
    """Tests de serialización de eventos."""

    @pytest.mark.integration
    def test_serialize_args_bytes(self, event_listener):
        """Test serializar bytes."""
        args = {
            'referenceId': bytes.fromhex('ab' * 32),
            'amount': 1000,
        }

        result = event_listener._serialize_args(args)

        assert result['referenceId'] == 'ab' * 32
        assert result['amount'] == 1000

    @pytest.mark.integration
    def test_serialize_args_big_int(self, event_listener):
        """Test serializar enteros grandes."""
        args = {
            'amount': 2**64,  # Mayor que JS max safe int
        }

        result = event_listener._serialize_args(args)

        assert result['amount'] == str(2**64)


# ==================== TESTS DE MÉTRICAS ====================

class TestMetrics:
    """Tests de métricas Prometheus."""

    @pytest.mark.integration
    def test_metrics_defined(self):
        """Test que las métricas están definidas."""
        from app.services.event_listener_service import (
            EVENTS_RECEIVED,
            EVENTS_PROCESSED,
            EVENTS_FAILED,
            EVENT_PROCESSING_TIME,
            LAST_PROCESSED_BLOCK,
            LISTENER_STATUS,
        )

        assert EVENTS_RECEIVED is not None
        assert EVENTS_PROCESSED is not None
        assert EVENTS_FAILED is not None
        assert EVENT_PROCESSING_TIME is not None
        assert LAST_PROCESSED_BLOCK is not None
        assert LISTENER_STATUS is not None


# ==================== TESTS DE BLOCKCHAIN EVENT ====================

class TestBlockchainEvent:
    """Tests de la clase BlockchainEvent."""

    @pytest.mark.integration
    def test_create_event(self):
        """Test crear evento blockchain."""
        event = BlockchainEvent(
            event_type=EventType.REMITTANCE_CREATED,
            tx_hash='0x' + 'a' * 64,
            block_number=1000000,
            block_timestamp=datetime.utcnow(),
            log_index=0,
            contract_address='0x' + '1' * 40,
            args={'amount': 1000},
        )

        assert event.event_type == EventType.REMITTANCE_CREATED
        assert event.block_number == 1000000
        assert 'amount' in event.args

    @pytest.mark.integration
    def test_event_id(self):
        """Test ID único de evento."""
        event = BlockchainEvent(
            event_type=EventType.REMITTANCE_CREATED,
            tx_hash='0xabc123',
            block_number=1000000,
            block_timestamp=datetime.utcnow(),
            log_index=5,
            contract_address='0x' + '1' * 40,
            args={},
        )

        assert event.id == '0xabc123_5'


# ==================== TESTS DE EVENT SUBSCRIPTION ====================

class TestEventSubscription:
    """Tests de suscripciones."""

    @pytest.mark.integration
    def test_create_subscription(self):
        """Test crear suscripción."""
        callback = MagicMock()
        sub = EventSubscription(
            event_type=EventType.REMITTANCE_CREATED,
            callback=callback,
            filter_params={'sender': '0x123'},
        )

        assert sub.event_type == EventType.REMITTANCE_CREATED
        assert sub.callback == callback
        assert sub.filter_params['sender'] == '0x123'
