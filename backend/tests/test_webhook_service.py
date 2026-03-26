"""
Tests para el Webhook Service.

Tests unitarios para:
- Envío de webhooks
- Firma y verificación
- Reintentos
- Endpoints
- PubSub
"""
import pytest
import asyncio
import json
import hmac
import hashlib
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.webhook_service import (
    WebhookService,
    WebhookPayload,
    WebhookEndpoint,
    WebhookEvent,
    DeliveryError,
    WEBHOOK_SECRET,
)


# ==================== FIXTURES ====================

@pytest.fixture
def mock_db():
    """Mock de sesión de base de datos."""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.add = MagicMock()
    db.commit = MagicMock()
    return db


@pytest.fixture
def mock_redis():
    """Mock de Redis."""
    redis_mock = MagicMock()
    redis_mock.ping.return_value = True
    redis_mock.publish = MagicMock()
    return redis_mock


@pytest.fixture
def webhook_service(mock_db, mock_redis):
    """Instancia del WebhookService con mocks."""
    with patch('app.services.webhook_service.SessionLocal', return_value=mock_db):
        with patch('app.services.webhook_service.redis.from_url', return_value=mock_redis):
            service = WebhookService(db=mock_db)
            service._redis = mock_redis
            return service


@pytest.fixture
def sample_endpoint():
    """Endpoint de prueba."""
    return WebhookEndpoint(
        id=str(uuid4()),
        url="https://api.example.com/webhook",
        secret="test-secret-123",
        events=["remittance.*", "alert.*"],
        enabled=True,
    )


@pytest.fixture
def sample_payload():
    """Payload de prueba."""
    return WebhookPayload(
        id=str(uuid4()),
        event="remittance.created",
        timestamp=datetime.utcnow().isoformat(),
        data={
            "remittance_id": str(uuid4()),
            "amount": 1000.00,
            "currency": "USD",
        },
    )


# ==================== TESTS DE PAYLOAD ====================

class TestWebhookPayload:
    """Tests de WebhookPayload."""

    @pytest.mark.integration
    def test_create_payload(self, sample_payload):
        """Test crear payload."""
        assert sample_payload.id is not None
        assert sample_payload.event == "remittance.created"
        assert "remittance_id" in sample_payload.data

    @pytest.mark.integration
    def test_to_dict(self, sample_payload):
        """Test convertir a diccionario."""
        d = sample_payload.to_dict()

        assert d['id'] == sample_payload.id
        assert d['event'] == sample_payload.event
        assert d['timestamp'] == sample_payload.timestamp
        assert d['data'] == sample_payload.data

    @pytest.mark.integration
    def test_to_json(self, sample_payload):
        """Test convertir a JSON."""
        j = sample_payload.to_json()

        parsed = json.loads(j)
        assert parsed['id'] == sample_payload.id
        assert parsed['event'] == sample_payload.event


# ==================== TESTS DE ENDPOINT ====================

class TestWebhookEndpoint:
    """Tests de WebhookEndpoint."""

    @pytest.mark.integration
    def test_matches_event_exact(self, sample_endpoint):
        """Test match exacto."""
        sample_endpoint.events = ["remittance.created"]
        assert sample_endpoint.matches_event("remittance.created") is True
        assert sample_endpoint.matches_event("remittance.released") is False

    @pytest.mark.integration
    def test_matches_event_wildcard(self, sample_endpoint):
        """Test match con wildcard."""
        assert sample_endpoint.matches_event("remittance.created") is True
        assert sample_endpoint.matches_event("remittance.released") is True
        assert sample_endpoint.matches_event("alert.low_balance") is True
        assert sample_endpoint.matches_event("system.maintenance") is False

    @pytest.mark.integration
    def test_matches_event_multiple_patterns(self):
        """Test con múltiples patrones."""
        endpoint = WebhookEndpoint(
            id="1",
            url="https://example.com",
            secret="secret",
            events=["remittance.created", "alert.*", "system.maintenance"],
        )

        assert endpoint.matches_event("remittance.created") is True
        assert endpoint.matches_event("remittance.released") is False
        assert endpoint.matches_event("alert.discrepancy") is True
        assert endpoint.matches_event("system.maintenance") is True


# ==================== TESTS DE FIRMA ====================

class TestSignature:
    """Tests de firma de webhooks."""

    @pytest.mark.integration
    def test_sign_payload(self, webhook_service, sample_payload):
        """Test firmar payload."""
        payload_json = sample_payload.to_json()
        signature = webhook_service._sign_payload(payload_json, "test-secret")

        assert signature is not None
        assert len(signature) == 64  # SHA256 hex

    @pytest.mark.integration
    def test_verify_signature_valid(self):
        """Test verificar firma válida."""
        payload = '{"event": "test"}'
        secret = "test-secret"

        expected = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        is_valid = WebhookService.verify_signature(
            payload=payload,
            signature=f"sha256={expected}",
            secret=secret,
        )

        assert is_valid is True

    @pytest.mark.integration
    def test_verify_signature_invalid(self):
        """Test verificar firma inválida."""
        is_valid = WebhookService.verify_signature(
            payload='{"event": "test"}',
            signature="sha256=invalid_signature",
            secret="test-secret",
        )

        assert is_valid is False

    @pytest.mark.integration
    def test_verify_signature_missing_prefix(self):
        """Test verificar firma sin prefijo sha256=."""
        is_valid = WebhookService.verify_signature(
            payload='{"event": "test"}',
            signature="no_prefix_signature",
            secret="test-secret",
        )

        assert is_valid is False


# ==================== TESTS DE ENVÍO ====================

class TestWebhookDelivery:
    """Tests de entrega de webhooks."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_send_webhook(self, webhook_service, mock_redis):
        """Test enviar webhook."""
        webhook_id = await webhook_service.send(
            event="remittance.created",
            data={"amount": 100},
        )

        assert webhook_id is not None
        # Verificar que se publicó en Redis
        mock_redis.publish.assert_called()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_deliver_success(self, webhook_service, sample_endpoint, sample_payload, mock_db):
        """Test entrega exitosa."""
        with patch('app.services.webhook_service.aiohttp.ClientSession') as MockSession:
            # Mock del response
            mock_response = MagicMock()
            mock_response.status = 200

            # Mock del context manager del post
            mock_post_cm = AsyncMock()
            mock_post_cm.__aenter__.return_value = mock_response
            mock_post_cm.__aexit__.return_value = None

            # Mock de la sesión
            mock_session_instance = MagicMock()
            mock_session_instance.post.return_value = mock_post_cm

            # Mock del context manager de la sesión
            mock_session_cm = AsyncMock()
            mock_session_cm.__aenter__.return_value = mock_session_instance
            mock_session_cm.__aexit__.return_value = None
            MockSession.return_value = mock_session_cm

            webhook_service._endpoints[sample_endpoint.id] = sample_endpoint

            result = await webhook_service._deliver(sample_endpoint, sample_payload)

            assert result is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_deliver_failure_retry(self, webhook_service, sample_endpoint, sample_payload, mock_db):
        """Test reintento en fallo."""
        with patch('app.services.webhook_service.aiohttp.ClientSession') as MockSession:
            with patch('app.services.webhook_service.WEBHOOK_MAX_RETRIES', 1):
                with patch('app.services.webhook_service.WEBHOOK_RETRY_DELAY', 0):
                    # Mock del response con error
                    mock_response = MagicMock()
                    mock_response.status = 500
                    mock_response.text = AsyncMock(return_value="Server error")

                    # Mock del context manager del post
                    mock_post_cm = AsyncMock()
                    mock_post_cm.__aenter__.return_value = mock_response
                    mock_post_cm.__aexit__.return_value = None

                    # Mock de la sesión
                    mock_session_instance = MagicMock()
                    mock_session_instance.post.return_value = mock_post_cm

                    # Mock del context manager de la sesión
                    mock_session_cm = AsyncMock()
                    mock_session_cm.__aenter__.return_value = mock_session_instance
                    mock_session_cm.__aexit__.return_value = None
                    MockSession.return_value = mock_session_cm

                    webhook_service._endpoints[sample_endpoint.id] = sample_endpoint

                    result = await webhook_service._deliver(sample_endpoint, sample_payload)

                    assert result is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_deliver_to_disabled_endpoint(self, webhook_service, sample_endpoint, sample_payload):
        """Test entrega a endpoint deshabilitado."""
        sample_endpoint.enabled = False
        result = await webhook_service._deliver(sample_endpoint, sample_payload)
        assert result is False


# ==================== TESTS DE SUSCRIPCIONES ====================

class TestSubscriptions:
    """Tests de suscripciones locales."""

    @pytest.mark.integration
    def test_subscribe_local(self, webhook_service):
        """Test suscribir callback local."""
        callback = MagicMock()
        webhook_service.subscribe("remittance.*", callback)

        assert "remittance.*" in webhook_service._local_subscribers
        assert callback in webhook_service._local_subscribers["remittance.*"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_notify_local_sync_callback(self, webhook_service, sample_payload):
        """Test notificar callback síncrono."""
        callback = MagicMock()
        webhook_service.subscribe("remittance.*", callback)

        await webhook_service._notify_local("remittance.created", sample_payload)

        callback.assert_called_once_with(sample_payload)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_notify_local_async_callback(self, webhook_service, sample_payload):
        """Test notificar callback asíncrono."""
        callback = AsyncMock()
        webhook_service.subscribe("remittance.*", callback)

        await webhook_service._notify_local("remittance.created", sample_payload)

        callback.assert_called_once_with(sample_payload)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_notify_non_matching_pattern(self, webhook_service, sample_payload):
        """Test no notificar si patrón no coincide."""
        callback = MagicMock()
        webhook_service.subscribe("system.*", callback)

        await webhook_service._notify_local("remittance.created", sample_payload)

        callback.assert_not_called()


# ==================== TESTS DE REGISTRO DE ENDPOINTS ====================

class TestEndpointManagement:
    """Tests de gestión de endpoints."""

    @pytest.mark.integration
    def test_register_endpoint(self, webhook_service, mock_db):
        """Test registrar endpoint."""
        endpoint_id = webhook_service.register_endpoint(
            url="https://api.example.com/webhook",
            secret="secret123",
            events=["remittance.*"],
            name="Test Endpoint",
        )

        assert endpoint_id is not None
        assert endpoint_id in webhook_service._endpoints
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.integration
    def test_unregister_endpoint(self, webhook_service, sample_endpoint, mock_db):
        """Test eliminar endpoint."""
        webhook_service._endpoints[sample_endpoint.id] = sample_endpoint

        mock_endpoint_model = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_endpoint_model

        result = webhook_service.unregister_endpoint(sample_endpoint.id)

        assert result is True
        assert sample_endpoint.id not in webhook_service._endpoints

    @pytest.mark.integration
    def test_get_endpoints(self, webhook_service, sample_endpoint):
        """Test obtener lista de endpoints."""
        webhook_service._endpoints[sample_endpoint.id] = sample_endpoint

        endpoints = webhook_service.get_endpoints()

        assert len(endpoints) == 1
        assert endpoints[0]['id'] == sample_endpoint.id
        assert endpoints[0]['url'] == sample_endpoint.url


# ==================== TESTS DE PUBSUB ====================

class TestPubSub:
    """Tests de PubSub con Redis."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_publish_redis(self, webhook_service, sample_payload, mock_redis):
        """Test publicar en Redis."""
        await webhook_service._publish_redis(sample_payload)

        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args[0]
        assert call_args[0] == "fincore:webhooks"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_publish_redis_no_connection(self, webhook_service, sample_payload):
        """Test publicar sin conexión Redis."""
        webhook_service._redis = None

        # No debe lanzar excepción
        await webhook_service._publish_redis(sample_payload)


# ==================== TESTS DE WORKER ====================

class TestWorker:
    """Tests del worker de entrega."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_start_stop_worker(self, webhook_service):
        """Test iniciar y detener worker."""
        await webhook_service.start()
        assert webhook_service._running is True
        assert webhook_service._worker_task is not None

        await webhook_service.stop()
        assert webhook_service._running is False


# ==================== TESTS DE EVENTOS ====================

class TestWebhookEvents:
    """Tests de tipos de eventos."""

    @pytest.mark.integration
    def test_event_types_defined(self):
        """Test que los tipos de eventos están definidos."""
        assert WebhookEvent.REMITTANCE_CREATED.value == "remittance.created"
        assert WebhookEvent.REMITTANCE_LOCKED.value == "remittance.locked"
        assert WebhookEvent.REMITTANCE_COMPLETED.value == "remittance.completed"
        assert WebhookEvent.TX_CONFIRMED.value == "blockchain.tx.confirmed"
        assert WebhookEvent.ALERT_DISCREPANCY.value == "alert.discrepancy"


# ==================== TESTS DE MÉTRICAS ====================

class TestMetrics:
    """Tests de métricas Prometheus."""

    @pytest.mark.integration
    def test_metrics_defined(self):
        """Test que las métricas están definidas."""
        from app.services.webhook_service import (
            WEBHOOKS_SENT,
            WEBHOOK_LATENCY,
            WEBHOOK_QUEUE_SIZE,
            ACTIVE_CONNECTIONS,
        )

        assert WEBHOOKS_SENT is not None
        assert WEBHOOK_LATENCY is not None
        assert WEBHOOK_QUEUE_SIZE is not None
        assert ACTIVE_CONNECTIONS is not None


# ==================== TESTS DE ENTREGAS RECIENTES ====================

class TestDeliveryHistory:
    """Tests de historial de entregas."""

    @pytest.mark.integration
    def test_get_recent_deliveries(self, webhook_service, mock_db):
        """Test obtener entregas recientes."""
        mock_delivery = MagicMock()
        mock_delivery.id = uuid4()
        mock_delivery.endpoint_id = uuid4()
        mock_delivery.event = "remittance.created"
        mock_delivery.status = "success"
        mock_delivery.response_code = 200
        mock_delivery.created_at = datetime.utcnow()
        mock_delivery.delivered_at = datetime.utcnow()

        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_delivery]

        deliveries = webhook_service.get_recent_deliveries(limit=10)

        assert len(deliveries) == 1
        assert deliveries[0]['event'] == "remittance.created"
        assert deliveries[0]['status'] == "success"
