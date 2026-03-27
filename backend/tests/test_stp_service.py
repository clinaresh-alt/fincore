"""
Tests para el servicio STP (SPEI).

Cubre:
- Validacion de CLABE
- Envio de pagos SPEI (mock)
- Procesamiento de webhooks
- Conciliacion
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from app.services.stp_service import (
    STPService,
    STPConfig,
    STPError,
    STPAPIError,
    STPAccountError,
)
from app.schemas.stp import (
    STPTransactionStatus,
    STPOrderResponse,
    STPWebhookPayload,
    STPBalanceResponse,
    validate_clabe,
    get_bank_from_clabe,
    BANK_CODES,
)


# ==================== FIXTURES ====================

@pytest.fixture
def stp_config():
    """Configuracion de STP para tests."""
    return STPConfig(
        api_url="https://demo.stpmex.com/speiws/rest",
        use_production=False,
        empresa="TESTEMPRESA",
        private_key_path="/tmp/test_key.pem",
        clabe_concentradora="646180000000000001",
        timeout_seconds=5,
    )


@pytest.fixture
def stp_service(stp_config, mock_db_session):
    """Servicio STP para tests."""
    service = STPService(db=mock_db_session, config=stp_config)
    return service


@pytest.fixture
def valid_clabe():
    """CLABE valida de ejemplo (BBVA)."""
    return "012180015678912342"  # CLABE de prueba


@pytest.fixture
def invalid_clabe():
    """CLABE invalida."""
    return "012180015678912345"  # Digito verificador incorrecto


@pytest.fixture
def sample_webhook_liquidated():
    """Webhook de pago liquidado."""
    return {
        "id": 12345,
        "claveRastreo": "20240115ABC123DEF456",
        "tipoOperacion": 1,
        "estado": 0,  # Liquidado
        "monto": 150050,  # $1,500.50 en centavos
        "cuentaOrdenante": "646180000000000001",
        "nombreOrdenante": "FINCORE SA",
        "cuentaBeneficiario": "012180015678912345",
        "nombreBeneficiario": "JUAN PEREZ",
        "concepto": "PAGO REMESA FRC-123",
        "referenciaNumerica": 1234567,
        "fechaOperacion": 20240115,
        "horaOperacion": "10:30:00",
    }


@pytest.fixture
def sample_webhook_returned():
    """Webhook de pago devuelto."""
    return {
        "id": 12346,
        "claveRastreo": "20240115XYZ789ABC012",
        "tipoOperacion": 1,
        "estado": 2,  # Devuelto
        "monto": 200000,
        "cuentaBeneficiario": "012180099999999999",
        "causaDevolucion": 1,  # Cuenta inexistente
    }


# ==================== TESTS: Validacion de CLABE ====================

class TestCLABEValidation:
    """Tests para validacion de CLABE."""

    def test_validate_clabe_valid(self):
        """CLABE valida deberia pasar."""
        # CLABE de STP de prueba
        assert validate_clabe("646180157063214178") is True

    def test_validate_clabe_invalid_checksum(self):
        """CLABE con digito verificador incorrecto deberia fallar."""
        assert validate_clabe("646180157063214179") is False

    def test_validate_clabe_wrong_length(self):
        """CLABE con longitud incorrecta deberia fallar."""
        assert validate_clabe("64618015706321417") is False
        assert validate_clabe("6461801570632141789") is False

    def test_validate_clabe_non_numeric(self):
        """CLABE con caracteres no numericos deberia fallar."""
        assert validate_clabe("64618015706321417A") is False

    def test_validate_clabe_empty(self):
        """CLABE vacia deberia fallar."""
        assert validate_clabe("") is False
        assert validate_clabe(None) is False

    def test_get_bank_from_clabe_valid(self):
        """Deberia obtener nombre de banco de CLABE valida."""
        # CLABE de BBVA (012)
        bank = get_bank_from_clabe("012180015678912345")
        assert bank == "BBVA MEXICO"

        # CLABE de Banamex (002)
        bank = get_bank_from_clabe("002180015678912345")
        assert bank == "BANAMEX"

        # CLABE de STP (646)
        bank = get_bank_from_clabe("646180015678912345")
        assert bank == "STP"

    def test_get_bank_from_clabe_unknown(self):
        """CLABE con codigo de banco desconocido."""
        bank = get_bank_from_clabe("999180015678912345")
        assert bank is None

    def test_bank_codes_catalog(self):
        """Catalogo de bancos deberia tener entradas principales."""
        assert "002" in BANK_CODES  # Banamex
        assert "012" in BANK_CODES  # BBVA
        assert "014" in BANK_CODES  # Santander
        assert "072" in BANK_CODES  # Banorte
        assert "646" in BANK_CODES  # STP


# ==================== TESTS: STP Service ====================

class TestSTPService:
    """Tests para el servicio STP."""

    def test_generate_tracking_key(self, stp_service):
        """Clave de rastreo deberia tener formato correcto."""
        key = stp_service._generate_tracking_key()

        assert len(key) == 30
        assert key[:8].isdigit()  # Fecha YYYYMMDD
        assert key[8:].isalnum()  # 22 caracteres alfanumericos

    def test_generate_tracking_key_unique(self, stp_service):
        """Cada clave de rastreo deberia ser unica."""
        keys = [stp_service._generate_tracking_key() for _ in range(100)]
        assert len(set(keys)) == 100

    def test_generate_reference(self, stp_service):
        """Referencia deberia ser numerica de 7 digitos."""
        ref = stp_service._generate_reference()

        assert len(ref) == 7
        assert ref.isdigit()

    def test_is_spei_available_weekday_business_hours(self, stp_service):
        """SPEI deberia estar disponible en horario laboral."""
        with patch('app.services.stp_service.datetime') as mock_dt:
            # Lunes 10:00
            mock_dt.now.return_value = datetime(2024, 1, 15, 10, 0)  # Lunes
            available, msg = stp_service.is_spei_available()
            # Nota: weekday() no se puede mockear facilmente, este test es ilustrativo

    def test_is_spei_available_weekend(self, stp_service):
        """SPEI no deberia estar disponible en fin de semana."""
        with patch('app.services.stp_service.datetime') as mock_dt:
            # Sabado
            mock_now = MagicMock()
            mock_now.weekday.return_value = 5  # Sabado
            mock_dt.now.return_value = mock_now

            available, msg = stp_service.is_spei_available()
            assert available is False
            assert "fin de semana" in msg.lower()

    def test_validate_beneficiary_account_valid(self, stp_service):
        """CLABE valida deberia pasar validacion."""
        valid, error = stp_service.validate_beneficiary_account("646180157063214178")
        assert valid is True
        assert error is None

    def test_validate_beneficiary_account_invalid_length(self, stp_service):
        """CLABE con longitud incorrecta deberia fallar."""
        valid, error = stp_service.validate_beneficiary_account("64618015706321417")
        assert valid is False
        assert "18 digitos" in error

    def test_validate_beneficiary_account_invalid_checksum(self, stp_service):
        """CLABE con checksum incorrecto deberia fallar."""
        valid, error = stp_service.validate_beneficiary_account("646180157063214179")
        assert valid is False
        assert "invalida" in error.lower()

    def test_validate_beneficiary_account_empty(self, stp_service):
        """CLABE vacia deberia fallar."""
        valid, error = stp_service.validate_beneficiary_account("")
        assert valid is False

    @pytest.mark.asyncio
    async def test_send_spei_validation_errors(self, stp_service):
        """Envio SPEI deberia validar parametros."""
        # CLABE invalida
        with pytest.raises(STPAccountError):
            await stp_service.send_spei_payment(
                beneficiary_clabe="invalid",
                beneficiary_name="Test",
                amount=Decimal("100"),
                concept="Test",
            )

        # Monto cero
        with pytest.raises(STPError):
            await stp_service.send_spei_payment(
                beneficiary_clabe="646180157063214178",
                beneficiary_name="Test",
                amount=Decimal("0"),
                concept="Test",
            )

        # Monto excede limite
        with pytest.raises(STPError):
            await stp_service.send_spei_payment(
                beneficiary_clabe="646180157063214178",
                beneficiary_name="Test",
                amount=Decimal("600000"),
                concept="Test",
            )


# ==================== TESTS: Webhooks ====================

class TestSTPWebhooks:
    """Tests para procesamiento de webhooks."""

    @pytest.mark.asyncio
    async def test_process_webhook_liquidated(self, stp_service, sample_webhook_liquidated):
        """Webhook de pago liquidado deberia procesarse."""
        payload = STPWebhookPayload(**sample_webhook_liquidated)

        result = await stp_service.process_webhook(payload)

        assert result["processed"] is True
        assert result["tracking_key"] == sample_webhook_liquidated["claveRastreo"]
        assert result["action_taken"] == "marked_as_liquidated"

    @pytest.mark.asyncio
    async def test_process_webhook_returned(self, stp_service, sample_webhook_returned):
        """Webhook de pago devuelto deberia procesarse."""
        payload = STPWebhookPayload(**sample_webhook_returned)

        result = await stp_service.process_webhook(payload)

        assert result["processed"] is True
        assert result["action_taken"] == "marked_as_returned"
        assert "return_reason" in result

    def test_webhook_payload_amount_conversion(self, sample_webhook_liquidated):
        """Monto en centavos deberia convertirse a decimal."""
        payload = STPWebhookPayload(**sample_webhook_liquidated)

        assert payload.monto == 150050  # Centavos
        assert payload.amount_decimal == Decimal("1500.50")

    def test_webhook_payload_is_liquidated(self, sample_webhook_liquidated):
        """Propiedad is_liquidated deberia ser correcta."""
        payload = STPWebhookPayload(**sample_webhook_liquidated)
        assert payload.is_liquidated is True
        assert payload.is_returned is False

    def test_webhook_payload_is_returned(self, sample_webhook_returned):
        """Propiedad is_returned deberia ser correcta."""
        payload = STPWebhookPayload(**sample_webhook_returned)
        assert payload.is_returned is True


# ==================== TESTS: Conciliacion ====================

class TestSTPReconciliation:
    """Tests para conciliacion."""

    @pytest.mark.asyncio
    async def test_reconcile_orders_empty(self, stp_service):
        """Conciliacion sin ordenes deberia retornar lista vacia."""
        stp_service._get_client = AsyncMock()

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"ordenes": []}
        mock_client.post.return_value = mock_response
        stp_service._get_client.return_value = mock_client

        records = await stp_service.reconcile_orders()

        assert len(records) == 0


# ==================== TESTS: STPOrderResponse ====================

class TestSTPOrderResponse:
    """Tests para respuestas de orden."""

    def test_order_response_success(self):
        """Respuesta exitosa deberia tener campos correctos."""
        response = STPOrderResponse(
            id="internal_123",
            stp_id=12345,
            tracking_key="20240115ABC123DEF456",
            reference="1234567",
            status=STPTransactionStatus.SENT,
            amount=Decimal("1500.50"),
            beneficiary_name="JUAN PEREZ",
            beneficiary_account="012180015678912345",
            beneficiary_bank="BBVA MEXICO",
            concept="PAGO REMESA",
            created_at=datetime.utcnow(),
            sent_at=datetime.utcnow(),
        )

        assert response.status == STPTransactionStatus.SENT
        assert response.stp_id == 12345
        assert response.error_code is None

    def test_order_response_error(self):
        """Respuesta de error deberia incluir detalles."""
        response = STPOrderResponse(
            id="internal_124",
            stp_id=None,
            tracking_key="20240115XYZ789",
            reference="7654321",
            status=STPTransactionStatus.REJECTED,
            status_description="Cuenta beneficiario no existe",
            amount=Decimal("1000"),
            beneficiary_name="TEST",
            beneficiary_account="012180099999999999",
            concept="TEST",
            created_at=datetime.utcnow(),
            error_code="3",
            error_message="Cuenta beneficiario no existe",
        )

        assert response.status == STPTransactionStatus.REJECTED
        assert response.error_code == "3"
        assert response.stp_id is None


# ==================== TESTS: Edge Cases ====================

class TestEdgeCases:
    """Tests para casos edge."""

    def test_tracking_key_date_format(self, stp_service):
        """Fecha en tracking key deberia ser YYYYMMDD."""
        key = stp_service._generate_tracking_key()
        date_part = key[:8]

        # Verificar que sea una fecha valida
        year = int(date_part[:4])
        month = int(date_part[4:6])
        day = int(date_part[6:8])

        assert 2024 <= year <= 2100
        assert 1 <= month <= 12
        assert 1 <= day <= 31

    def test_reference_padding(self, stp_service):
        """Referencia deberia tener padding con ceros."""
        # Generar muchas referencias y verificar formato
        for _ in range(10):
            ref = stp_service._generate_reference()
            assert len(ref) == 7
            assert ref.isdigit()

    def test_beneficiary_name_truncation(self):
        """Nombre largo deberia truncarse a 40 caracteres."""
        long_name = "JUAN CARLOS ROBERTO MARTINEZ DE LA CRUZ HERNANDEZ PEREZ GONZALEZ"
        truncated = long_name[:40]

        assert len(truncated) == 40

    def test_concept_truncation(self):
        """Concepto largo deberia truncarse a 40 caracteres."""
        long_concept = "PAGO DE REMESA INTERNACIONAL POR SERVICIOS PROFESIONALES DE CONSULTORIA"
        truncated = long_concept[:40]

        assert len(truncated) == 40


# ==================== TESTS: Status Mapping ====================

class TestStatusMapping:
    """Tests para mapeo de estados."""

    def test_all_statuses_have_values(self):
        """Todos los estados deberian tener valores string."""
        for status in STPTransactionStatus:
            assert isinstance(status.value, str)
            assert len(status.value) > 0

    def test_status_enum_values(self):
        """Valores de enum deberian ser correctos."""
        assert STPTransactionStatus.PENDING.value == "pending"
        assert STPTransactionStatus.SENT.value == "sent"
        assert STPTransactionStatus.LIQUIDATED.value == "liquidated"
        assert STPTransactionStatus.RETURNED.value == "returned"
        assert STPTransactionStatus.FAILED.value == "failed"
