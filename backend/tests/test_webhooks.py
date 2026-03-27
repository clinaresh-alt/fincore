"""
Tests para el sistema de webhooks.

Prueba:
- Schemas de webhooks
- Procesamiento de webhooks entrantes (STP/Bitso)
- Endpoints de webhooks
- Verificación de firmas
"""
import pytest
import json
import hmac
import hashlib
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.schemas.webhooks import (
    WebhookSource,
    WebhookEventType,
    WebhookStatus,
    STPWebhookEvent,
    BitsoWebhookEvent,
    WebhookPayload,
    WebhookEndpoint,
    WebhookDelivery,
    WebhookSignatureVerifier,
    CreateWebhookEndpoint,
    RemittanceWebhookData,
)


# ============ Tests de Schemas ============

class TestSTPWebhookEvent:
    """Tests para STPWebhookEvent."""

    def test_create_stp_event(self):
        """Test crear evento STP."""
        event = STPWebhookEvent(
            id=12345,
            claveRastreo="FINCORE123456789",
            tipoOperacion=1,
            estado=0,
            monto=100000,  # 1000 pesos en centavos
            cuentaOrdenante="012180000100000001",
            nombreOrdenante="EMPRESA SA",
            cuentaBeneficiario="012180000200000002",
            nombreBeneficiario="JUAN PEREZ",
            concepto="Pago de remesa",
        )

        assert event.id == 12345
        assert event.claveRastreo == "FINCORE123456789"
        assert event.estado == 0

    def test_amount_decimal(self):
        """Test conversión de centavos a pesos."""
        event = STPWebhookEvent(
            id=1,
            claveRastreo="TEST123",
            tipoOperacion=1,
            estado=0,
            monto=123456,
        )

        assert event.amount_decimal == Decimal("1234.56")

    def test_is_liquidated(self):
        """Test detección de estado liquidado."""
        event = STPWebhookEvent(
            id=1,
            claveRastreo="TEST",
            tipoOperacion=1,
            estado=0,  # Liquidado
            monto=1000,
        )
        assert event.is_liquidated is True
        assert event.is_returned is False

    def test_is_returned(self):
        """Test detección de estado devuelto."""
        event = STPWebhookEvent(
            id=1,
            claveRastreo="TEST",
            tipoOperacion=1,
            estado=2,  # Devuelto
            monto=1000,
            causaDevolucion=1,
        )
        assert event.is_returned is True
        assert event.is_liquidated is False

    def test_event_type_liquidated(self):
        """Test tipo de evento para liquidación."""
        event = STPWebhookEvent(
            id=1,
            claveRastreo="TEST",
            tipoOperacion=1,
            estado=0,
            monto=1000,
        )
        assert event.event_type == WebhookEventType.STP_PAYMENT_LIQUIDATED

    def test_event_type_deposit(self):
        """Test tipo de evento para depósito."""
        event = STPWebhookEvent(
            id=1,
            claveRastreo="TEST",
            tipoOperacion=2,  # Recepción
            estado=0,
            monto=1000,
        )
        assert event.event_type == WebhookEventType.STP_DEPOSIT_RECEIVED


class TestBitsoWebhookEvent:
    """Tests para BitsoWebhookEvent."""

    def test_create_bitso_event(self):
        """Test crear evento Bitso."""
        event = BitsoWebhookEvent(
            type="order.completed",
            payload={
                "oid": "order123",
                "book": "usdc_mxn",
                "price": "17.50",
                "amount": "100.00",
            },
            created_at=datetime.utcnow(),
        )

        assert event.type == "order.completed"
        assert event.order_id == "order123"

    def test_event_type_mapping(self):
        """Test mapeo de tipos de evento."""
        event = BitsoWebhookEvent(
            type="withdrawal.complete",
            payload={"wid": "wd123"},
            created_at=datetime.utcnow(),
        )
        assert event.event_type == WebhookEventType.BITSO_WITHDRAWAL_COMPLETE

    def test_withdrawal_id(self):
        """Test obtener ID de retiro."""
        event = BitsoWebhookEvent(
            type="withdrawal.pending",
            payload={"wid": "withdrawal_456"},
            created_at=datetime.utcnow(),
        )
        assert event.withdrawal_id == "withdrawal_456"


class TestWebhookPayload:
    """Tests para WebhookPayload."""

    def test_create_payload(self):
        """Test crear payload de webhook."""
        payload = WebhookPayload(
            id="wh_123",
            event=WebhookEventType.REMITTANCE_COMPLETED,
            data={
                "remittance_id": "rem_456",
                "amount": 1000.00,
            },
            remittance_id="rem_456",
        )

        assert payload.id == "wh_123"
        assert payload.event == WebhookEventType.REMITTANCE_COMPLETED
        assert payload.data["remittance_id"] == "rem_456"

    def test_to_dict(self):
        """Test conversión a diccionario."""
        payload = WebhookPayload(
            id="wh_123",
            event=WebhookEventType.REMITTANCE_CREATED,
            data={"test": "data"},
        )

        d = payload.to_dict()
        assert d["id"] == "wh_123"
        assert d["event"] == "remittance.created"
        assert "created_at" in d

    def test_sign_payload(self):
        """Test firma de payload."""
        payload = WebhookPayload(
            id="wh_123",
            event=WebhookEventType.REMITTANCE_CREATED,
            data={"test": "data"},
        )

        secret = "test_secret"
        signature = payload.sign(secret)

        # Verificar que la firma es consistente
        assert len(signature) == 64  # SHA256 hex
        assert signature == payload.sign(secret)  # Misma entrada = misma firma


class TestWebhookSignatureVerifier:
    """Tests para verificación de firmas."""

    def test_verify_valid_signature(self):
        """Test verificar firma válida."""
        payload = b'{"test": "data"}'
        secret = "my_secret"

        # Generar firma correcta
        signature = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        assert WebhookSignatureVerifier.verify_stp_signature(
            payload, signature, secret
        ) is True

    def test_verify_invalid_signature(self):
        """Test verificar firma inválida."""
        payload = b'{"test": "data"}'
        secret = "my_secret"
        wrong_signature = "wrong_signature_here"

        assert WebhookSignatureVerifier.verify_stp_signature(
            payload, wrong_signature, secret
        ) is False

    def test_generate_signature(self):
        """Test generar firma para webhook saliente."""
        payload = {"event": "test", "data": {"id": 123}}
        secret = "webhook_secret"

        signature = WebhookSignatureVerifier.generate_signature(payload, secret)

        # Verificar que la firma es correcta
        expected = hmac.new(
            secret.encode(),
            json.dumps(payload, sort_keys=True).encode(),
            hashlib.sha256
        ).hexdigest()

        assert signature == expected


class TestCreateWebhookEndpoint:
    """Tests para validación de endpoint."""

    def test_valid_https_url(self):
        """Test URL HTTPS válida."""
        endpoint = CreateWebhookEndpoint(
            url="https://api.example.com/webhooks",
            events=[WebhookEventType.REMITTANCE_COMPLETED],
        )
        assert str(endpoint.url) == "https://api.example.com/webhooks"

    def test_invalid_http_url(self):
        """Test URL HTTP inválida."""
        with pytest.raises(ValueError, match="HTTPS"):
            CreateWebhookEndpoint(
                url="http://api.example.com/webhooks",
                events=[],
            )


# ============ Tests de Webhook Processing ============

class TestWebhookProcessing:
    """Tests para procesamiento de webhooks."""

    @pytest.fixture
    def mock_db(self):
        """Mock de sesión de base de datos."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_process_stp_liquidated(self, mock_db):
        """Test procesar webhook STP liquidado."""
        from app.services.webhook_service import InboundWebhookProcessor

        # Mock de remesa
        mock_remittance = MagicMock()
        mock_remittance.id = "rem_123"
        mock_remittance.reference_code = "REF123"
        mock_remittance.amount_fiat_destination = Decimal("1000.00")

        mock_db.query.return_value.filter.return_value.first.return_value = mock_remittance

        processor = InboundWebhookProcessor(mock_db)

        payload = json.dumps({
            "id": 12345,
            "claveRastreo": "FINCORE123",
            "tipoOperacion": 1,
            "estado": 0,  # Liquidado
            "monto": 100000,
        }).encode()

        with patch.object(processor, '_get_webhook_service') as mock_ws:
            mock_ws.return_value.send = AsyncMock()

            result = await processor.process_stp_webhook(payload)

            assert result["action"] == "completed"
            assert result["remittance_id"] == "rem_123"

    @pytest.mark.asyncio
    async def test_process_stp_returned(self, mock_db):
        """Test procesar webhook STP devuelto."""
        from app.services.webhook_service import InboundWebhookProcessor

        mock_remittance = MagicMock()
        mock_remittance.id = "rem_456"
        mock_remittance.reference_code = "REF456"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_remittance

        processor = InboundWebhookProcessor(mock_db)

        payload = json.dumps({
            "id": 12346,
            "claveRastreo": "FINCORE456",
            "tipoOperacion": 1,
            "estado": 2,  # Devuelto
            "monto": 50000,
            "causaDevolucion": 1,  # Cuenta inexistente
        }).encode()

        with patch.object(processor, '_get_webhook_service') as mock_ws:
            mock_ws.return_value.send = AsyncMock()

            result = await processor.process_stp_webhook(payload)

            assert result["action"] == "returned"
            assert result["reason"] == "Cuenta inexistente"

    @pytest.mark.asyncio
    async def test_process_bitso_order_completed(self, mock_db):
        """Test procesar webhook Bitso orden completada."""
        from app.services.webhook_service import InboundWebhookProcessor

        mock_remittance = MagicMock()
        mock_remittance.id = "rem_789"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_remittance

        processor = InboundWebhookProcessor(mock_db)

        payload = json.dumps({
            "type": "order.completed",
            "payload": {
                "oid": "order_xyz",
                "price": "17.85",
                "amount": "100.00",
            },
            "created_at": datetime.utcnow().isoformat(),
        }).encode()

        result = await processor.process_bitso_webhook(payload)

        assert result["action"] == "order_completed"

    @pytest.mark.asyncio
    async def test_process_unknown_event(self, mock_db):
        """Test procesar evento desconocido."""
        from app.services.webhook_service import InboundWebhookProcessor

        processor = InboundWebhookProcessor(mock_db)

        payload = json.dumps({
            "type": "unknown.event",
            "payload": {},
            "created_at": datetime.utcnow().isoformat(),
        }).encode()

        result = await processor.process_bitso_webhook(payload)

        assert result["action"] == "unknown"


# ============ Tests de Webhook Endpoints ============

class TestWebhookEndpoints:
    """Tests para endpoints de webhooks."""

    @pytest.fixture
    def client(self):
        """Cliente de prueba FastAPI."""
        from app.main import app
        return TestClient(app)

    def test_webhook_status(self, client):
        """Test endpoint de status."""
        response = client.get("/api/v1/webhooks/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "endpoints" in data

    def test_webhook_test_endpoint(self, client):
        """Test endpoint de prueba."""
        response = client.get("/api/v1/webhooks/test")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_receive_stp_webhook(self, client):
        """Test recibir webhook STP."""
        payload = {
            "id": 123,
            "claveRastreo": "TEST123",
            "tipoOperacion": 1,
            "estado": 0,
            "monto": 10000,
        }

        with patch('app.api.v1.endpoints.webhooks.get_inbound_webhook_processor') as mock_proc:
            mock_processor = MagicMock()
            mock_processor.process_stp_webhook = AsyncMock(return_value={
                "success": True,
                "message": "Processed",
            })
            mock_proc.return_value = mock_processor

            response = client.post(
                "/api/v1/webhooks/stp",
                json=payload,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_receive_bitso_webhook(self, client):
        """Test recibir webhook Bitso."""
        payload = {
            "type": "order.completed",
            "payload": {"oid": "test_order"},
            "created_at": datetime.utcnow().isoformat(),
        }

        with patch('app.api.v1.endpoints.webhooks.get_inbound_webhook_processor') as mock_proc:
            mock_processor = MagicMock()
            mock_processor.process_bitso_webhook = AsyncMock(return_value={
                "success": True,
                "message": "Processed",
            })
            mock_proc.return_value = mock_processor

            response = client.post(
                "/api/v1/webhooks/bitso",
                json=payload,
            )

            assert response.status_code == 200

    def test_receive_invalid_source(self, client):
        """Test recibir webhook con source inválido."""
        response = client.post(
            "/api/v1/webhooks/receive/invalid",
            json={},
        )
        assert response.status_code == 400
        assert "Source inválido" in response.json()["detail"]


# ============ Tests de Webhook Delivery ============

class TestWebhookDelivery:
    """Tests para entrega de webhooks salientes."""

    def test_webhook_delivery_model(self):
        """Test modelo de entrega."""
        payload = WebhookPayload(
            id="wh_1",
            event=WebhookEventType.REMITTANCE_COMPLETED,
            data={},
        )

        delivery = WebhookDelivery(
            id="del_1",
            endpoint_id="ep_1",
            payload=payload,
        )

        assert delivery.status == WebhookStatus.PENDING
        assert delivery.attempt_count == 0
        assert delivery.last_attempt is None


# ============ Tests de Remittance Webhook Data ============

class TestRemittanceWebhookData:
    """Tests para datos de webhook de remesa."""

    def test_create_remittance_data(self):
        """Test crear datos de remesa para webhook."""
        data = RemittanceWebhookData(
            remittance_id="rem_123",
            reference_code="REF123",
            status="completed",
            amount_source=Decimal("100.00"),
            currency_source="USDC",
            amount_destination=Decimal("1750.00"),
            currency_destination="MXN",
            recipient_name="Juan Pérez",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            spei_tracking_key="FINCORE123456",
        )

        assert data.remittance_id == "rem_123"
        assert data.amount_source == Decimal("100.00")
        assert data.spei_tracking_key == "FINCORE123456"


# ============ Tests de Enums ============

class TestWebhookEnums:
    """Tests para enums de webhooks."""

    def test_webhook_source_values(self):
        """Test valores de WebhookSource."""
        assert WebhookSource.STP.value == "stp"
        assert WebhookSource.BITSO.value == "bitso"
        assert WebhookSource.BLOCKCHAIN.value == "blockchain"

    def test_webhook_event_type_values(self):
        """Test valores de WebhookEventType."""
        assert WebhookEventType.STP_PAYMENT_LIQUIDATED.value == "stp.payment.liquidated"
        assert WebhookEventType.BITSO_ORDER_COMPLETED.value == "bitso.order.completed"
        assert WebhookEventType.REMITTANCE_COMPLETED.value == "remittance.completed"

    def test_webhook_status_values(self):
        """Test valores de WebhookStatus."""
        assert WebhookStatus.PENDING.value == "pending"
        assert WebhookStatus.DELIVERED.value == "delivered"
        assert WebhookStatus.FAILED.value == "failed"
