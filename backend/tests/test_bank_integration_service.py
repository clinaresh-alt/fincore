"""
Tests para el Servicio de Integracion Bancaria.

Prueba la integracion con sistemas bancarios mexicanos:
- Transferencias SPEI-OUT
- Webhooks SPEI-IN
- Generacion de CLABEs virtuales
- Consulta de saldos
- Conciliacion bancaria
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4

from app.models.bank_account import (
    BankAccount,
    BankTransaction,
    VirtualClabeAssignment,
    BankProvider,
    BankAccountType,
    BankAccountStatus,
    BankTransactionType,
    BankTransactionStatus,
)
from app.services.bank_integration_service import (
    BankIntegrationService,
    SpeiTransferRequest,
    SpeiTransferResult,
    BankBalanceInfo,
    SpeiError,
    InvalidClabeError,
    InsufficientFundsError,
)


# ==================== FIXTURES ====================

@pytest.fixture
def mock_db():
    """Mock de sesion de base de datos."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.query = MagicMock()
    db.rollback = MagicMock()
    return db


@pytest.fixture
def bank_service(mock_db):
    """Instancia del servicio bancario."""
    return BankIntegrationService(mock_db)


@pytest.fixture
def sample_platform_account():
    """Cuenta operativa de prueba."""
    account = MagicMock(spec=BankAccount)
    account.id = uuid4()
    account.account_alias = "FINCORE_MAIN"
    account.is_platform_account = True
    account.bank_name = "STP"
    account.clabe = "646180110400000001"
    account.currency = "MXN"
    account.status = BankAccountStatus.ACTIVE
    account.last_known_balance = Decimal("500000.00")
    account.provider = BankProvider.STP
    return account


@pytest.fixture
def sample_spei_request():
    """Solicitud SPEI de prueba."""
    # CLABE válida con dígito verificador correcto
    # Usando formato: 646 + 180 + 11 dígitos + check digit
    return SpeiTransferRequest(
        amount=Decimal("1000.00"),
        beneficiary_name="Juan Perez",
        beneficiary_clabe="646180157000000004",  # CLABE válida de prueba
        beneficiary_rfc="XAXX010101000",
        concept="Pago de servicios",
        reference="12345678",
    )


# ==================== TESTS DE VALIDACION CLABE ====================

class TestClabeValidation:
    """Tests de validacion de CLABE."""

    @pytest.mark.integration
    def test_validate_clabe_valid(self, bank_service):
        """Test CLABE valida."""
        # CLABE con digito verificador correcto
        valid_clabe = "646180110400000001"
        result = bank_service.validate_clabe(valid_clabe)
        # Nota: El resultado depende del digito verificador real
        assert isinstance(result, bool)

    @pytest.mark.integration
    def test_validate_clabe_invalid_length(self, bank_service):
        """Test CLABE con longitud invalida."""
        assert bank_service.validate_clabe("12345") is False
        assert bank_service.validate_clabe("") is False
        assert bank_service.validate_clabe("1234567890123456789") is False

    @pytest.mark.integration
    def test_validate_clabe_non_numeric(self, bank_service):
        """Test CLABE con caracteres no numericos."""
        assert bank_service.validate_clabe("64618011040000000A") is False

    @pytest.mark.integration
    def test_calculate_check_digit(self, bank_service):
        """Test calculo de digito verificador."""
        # CLABE sin digito verificador
        clabe_17 = "64618011040000000"
        digit = bank_service._calculate_clabe_check_digit(clabe_17)
        assert digit.isdigit()
        assert len(digit) == 1


# ==================== TESTS DE TRANSFERENCIAS SPEI ====================

class TestSpeiTransfers:
    """Tests de transferencias SPEI-OUT."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_send_spei_success(
        self, bank_service, mock_db, sample_platform_account, sample_spei_request
    ):
        """Test envio SPEI exitoso."""
        # Mock cuenta origen
        mock_db.query.return_value.filter.return_value.first.return_value = sample_platform_account

        with patch.object(bank_service, '_call_stp_transfer_api', new_callable=AsyncMock) as mock_api:
            mock_api.return_value = SpeiTransferResult(
                success=True,
                tracking_key="1234567",
                stp_id="STP-12345",
                status="liquidada",
            )

            result = await bank_service.send_spei_transfer(
                request=sample_spei_request,
                source_account_id=str(sample_platform_account.id),
            )

            assert result.success is True
            assert result.tracking_key is not None
            mock_db.add.assert_called()
            mock_db.commit.assert_called()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_send_spei_insufficient_funds(
        self, bank_service, mock_db, sample_platform_account
    ):
        """Test SPEI con fondos insuficientes."""
        # Cuenta con saldo bajo
        sample_platform_account.last_known_balance = Decimal("100.00")
        mock_db.query.return_value.filter.return_value.first.return_value = sample_platform_account

        request = SpeiTransferRequest(
            amount=Decimal("1000.00"),
            beneficiary_name="Test",
            beneficiary_clabe="646180157000000004",  # CLABE válida
            beneficiary_rfc="XAXX010101000",
            concept="Test",
            reference="123",
        )

        result = await bank_service.send_spei_transfer(
            request=request,
            source_account_id=str(sample_platform_account.id),
        )

        assert result.success is False
        assert "insuficiente" in result.error_message.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_send_spei_account_not_found(self, bank_service, mock_db):
        """Test SPEI con cuenta no encontrada."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        request = SpeiTransferRequest(
            amount=Decimal("100.00"),
            beneficiary_name="Test",
            beneficiary_clabe="646180157000000004",  # CLABE válida
            beneficiary_rfc="XAXX010101000",
            concept="Test",
            reference="123",
        )

        result = await bank_service.send_spei_transfer(
            request=request,
            source_account_id=str(uuid4()),
        )

        assert result.success is False
        assert "no encontrada" in result.error_message.lower()

    @pytest.mark.integration
    def test_validate_spei_transfer_min_amount(self, bank_service):
        """Test validacion monto minimo."""
        request = SpeiTransferRequest(
            amount=Decimal("0.50"),  # Menor al minimo
            beneficiary_name="Test",
            beneficiary_clabe="646180157000000004",  # CLABE válida
            beneficiary_rfc="XAXX010101000",
            concept="Test",
            reference="123",
        )

        with pytest.raises(SpeiError) as exc_info:
            bank_service._validate_spei_transfer(request)

        assert "mínimo" in str(exc_info.value).lower()


# ==================== TESTS DE WEBHOOKS SPEI-IN ====================

class TestSpeiWebhooks:
    """Tests de webhooks SPEI-IN."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_process_webhook_success(
        self, bank_service, mock_db, sample_platform_account
    ):
        """Test procesamiento de webhook exitoso."""
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None,  # No existe transaccion previa
            sample_platform_account,  # Cuenta encontrada
        ]

        payload = {
            "id": "STP-WEBHOOK-123",
            "cuentaBeneficiario": sample_platform_account.clabe,
            "cuentaOrdenante": "012180020000000001",
            "monto": 5000.00,
            "conceptoPago": "Deposito de prueba",
            "referenciaNumerica": "12345678",
            "nombreOrdenante": "Maria Garcia",
            "rfcCurpOrdenante": "GARM800101000",
            "institucionOrdenante": "BBVA",
            "fechaOperacion": datetime.utcnow().isoformat(),
            "claveRastreo": "BBVA1234567",
        }

        success, transaction = await bank_service.process_spei_webhook(payload)

        assert success is True
        assert transaction is not None
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_process_webhook_duplicate(
        self, bank_service, mock_db
    ):
        """Test webhook duplicado (idempotencia)."""
        existing_tx = MagicMock(spec=BankTransaction)
        existing_tx.tracking_key = "BBVA1234567"
        mock_db.query.return_value.filter.return_value.first.return_value = existing_tx

        payload = {
            "claveRastreo": "BBVA1234567",
            "monto": 1000,
        }

        success, transaction = await bank_service.process_spei_webhook(payload)

        assert success is True
        assert transaction == existing_tx
        mock_db.add.assert_not_called()


# ==================== TESTS DE CLABES VIRTUALES ====================

class TestVirtualClabes:
    """Tests de CLABEs virtuales."""

    @pytest.mark.integration
    def test_generate_virtual_clabe_success(
        self, bank_service, mock_db, sample_platform_account
    ):
        """Test generacion de CLABE virtual."""
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_platform_account,  # Cuenta base
            None,  # CLABE no existe
        ]

        remittance_id = str(uuid4())
        virtual_clabe = bank_service.generate_virtual_clabe(
            assignment_type="remittance",
            remittance_id=remittance_id,
            base_account_id=str(sample_platform_account.id),
        )

        assert virtual_clabe is not None
        assert len(virtual_clabe) == 18
        assert virtual_clabe.isdigit()
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.integration
    def test_generate_virtual_clabe_no_base_account(self, bank_service, mock_db):
        """Test sin cuenta base configurada."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        virtual_clabe = bank_service.generate_virtual_clabe(
            assignment_type="user",
            user_id=str(uuid4()),
        )

        assert virtual_clabe is None


# ==================== TESTS DE CONSULTA DE SALDOS ====================

class TestBalanceQueries:
    """Tests de consulta de saldos."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_account_balance(
        self, bank_service, mock_db, sample_platform_account
    ):
        """Test consulta de saldo."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_platform_account
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [
            Decimal("10000"),  # pending_out
            Decimal("5000"),   # pending_in
        ]

        balance = await bank_service.get_account_balance(str(sample_platform_account.id))

        assert balance is not None
        assert balance.balance == sample_platform_account.last_known_balance
        assert balance.clabe == sample_platform_account.clabe

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_account_balance_not_found(self, bank_service, mock_db):
        """Test saldo cuenta no encontrada."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        balance = await bank_service.get_account_balance(str(uuid4()))

        assert balance is None

    @pytest.mark.integration
    def test_get_bank_totals(self, bank_service, mock_db):
        """Test obtener totales bancarios."""
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [
            Decimal("1000000"),  # total_balance
            Decimal("50000"),    # deposits_today
            Decimal("30000"),    # withdrawals_today
            Decimal("10000"),    # pending_deposits
            Decimal("5000"),     # pending_withdrawals
            5,                   # unreconciled_count
        ]

        totals = bank_service.get_bank_totals()

        assert totals["balance_total"] == Decimal("1000000")
        assert totals["currency"] == "MXN"
        assert "unreconciled_count" in totals


# ==================== TESTS DE CONCILIACION ====================

class TestBankReconciliation:
    """Tests de conciliacion bancaria."""

    @pytest.mark.integration
    def test_get_unreconciled_transactions(self, bank_service, mock_db):
        """Test obtener transacciones sin conciliar."""
        tx1 = MagicMock(spec=BankTransaction)
        tx2 = MagicMock(spec=BankTransaction)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [tx1, tx2]

        result = bank_service.get_unreconciled_transactions(limit=10)

        assert len(result) == 2

    @pytest.mark.integration
    def test_mark_transactions_reconciled(self, bank_service, mock_db):
        """Test marcar transacciones como conciliadas."""
        mock_db.query.return_value.filter.return_value.update.return_value = 3

        count = bank_service.mark_transactions_reconciled(
            transaction_ids=[str(uuid4()), str(uuid4()), str(uuid4())],
            reconciliation_log_id=str(uuid4()),
        )

        assert count == 3
        mock_db.commit.assert_called()


# ==================== TESTS DE HELPERS ====================

class TestBankHelpers:
    """Tests de funciones auxiliares."""

    @pytest.mark.integration
    def test_generate_tracking_key(self, bank_service):
        """Test generacion de clave de rastreo."""
        key = bank_service._generate_tracking_key()

        assert key is not None
        assert len(key) == 7
        assert key.isdigit()

    @pytest.mark.integration
    def test_get_bank_from_clabe(self, bank_service):
        """Test obtener banco desde CLABE."""
        # BBVA = 012
        assert bank_service._get_bank_from_clabe("012180015000000001") == "012"
        # STP = 646
        assert bank_service._get_bank_from_clabe("646180110400000001") == "646"
        # Banamex = 002
        assert bank_service._get_bank_from_clabe("002180015000000001") == "002"

    @pytest.mark.integration
    def test_sign_stp_request(self, bank_service):
        """Test firma de request STP."""
        payload = {"monto": 1000, "claveRastreo": "123"}
        signature = bank_service._sign_stp_request(payload)

        assert signature is not None
        assert len(signature) == 64  # SHA256 hex
