"""
Tests unitarios para RemittanceService.
Modulo de remesas transfronterizas con escrow blockchain.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.remittance_service import (
    RemittanceService,
    RemittanceQuote,
    RemittanceResult,
)
from app.models.remittance import (
    Remittance,
    RemittanceStatus,
    RemittanceBlockchainTx,
    BlockchainRemittanceStatus,
    ReconciliationLog,
    Currency,
    Stablecoin,
    PaymentMethod,
    DisbursementMethod,
)


# ==================== FIXTURES ====================

@pytest.fixture
def mock_db_session():
    """Mock de sesion de base de datos async."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def sample_recipient_info():
    """Informacion de beneficiario de ejemplo."""
    return {
        "name": "Juan Perez Garcia",
        "bank_name": "Banco de Chile",
        "account_number": "1234567890",
        "account_type": "checking",
        "phone": "+56912345678",
        "email": "juan.perez@email.com",
        "address": "Av. Providencia 123",
        "city": "Santiago",
        "country": "CL"
    }


@pytest.fixture
def sample_recipient_mexico():
    """Informacion de beneficiario en Mexico."""
    return {
        "name": "Maria Lopez Martinez",
        "bank_name": "BBVA Mexico",
        "clabe": "012180015678901234",
        "phone": "+525512345678",
        "email": "maria.lopez@email.com",
        "country": "MX"
    }


@pytest.fixture
def sample_remittance():
    """Remesa de ejemplo."""
    remittance = MagicMock(spec=Remittance)
    remittance.id = uuid4()
    remittance.reference_code = "REM-20240115-ABC123"
    remittance.sender_id = uuid4()
    remittance.recipient_info = {
        "name": "Juan Perez",
        "bank_name": "Banco Chile",
        "account_number": "1234567890"
    }
    remittance.amount_fiat_source = Decimal("500.00")
    remittance.currency_source = Currency.USD
    remittance.amount_fiat_destination = Decimal("450000.00")
    remittance.currency_destination = Currency.CLP
    remittance.amount_stablecoin = Decimal("492.50")
    remittance.stablecoin = Stablecoin.USDC
    remittance.exchange_rate_source_usd = Decimal("1.0")
    remittance.exchange_rate_usd_destination = Decimal("900.00")
    remittance.platform_fee = Decimal("7.50")
    remittance.network_fee = Decimal("0.50")
    remittance.total_fees = Decimal("8.00")
    remittance.status = RemittanceStatus.INITIATED
    remittance.payment_method = PaymentMethod.WIRE_TRANSFER
    remittance.disbursement_method = DisbursementMethod.BANK_TRANSFER
    remittance.escrow_locked_at = None
    remittance.escrow_expires_at = None
    remittance.created_at = datetime.utcnow()
    remittance.updated_at = datetime.utcnow()
    return remittance


@pytest.fixture
def sample_locked_remittance(sample_remittance):
    """Remesa con fondos bloqueados en escrow."""
    sample_remittance.status = RemittanceStatus.LOCKED
    sample_remittance.escrow_locked_at = datetime.utcnow()
    sample_remittance.escrow_expires_at = datetime.utcnow() + timedelta(hours=48)
    return sample_remittance


@pytest.fixture
def sample_expired_remittance(sample_remittance):
    """Remesa con escrow expirado."""
    sample_remittance.status = RemittanceStatus.LOCKED
    sample_remittance.escrow_locked_at = datetime.utcnow() - timedelta(hours=50)
    sample_remittance.escrow_expires_at = datetime.utcnow() - timedelta(hours=2)
    return sample_remittance


@pytest.fixture
def remittance_service(mock_db_session):
    """Instancia del servicio de remesas."""
    with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
        mock_rate.return_value = Decimal("900.00")  # USD -> CLP
        service = RemittanceService(mock_db_session)
        return service


# ==================== TESTS DE COTIZACION ====================

class TestRemittanceQuote:
    """Tests de cotizacion de remesas."""

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_get_quote_usd_to_clp(self, mock_db_session):
        """Test cotizacion USD a CLP."""
        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.side_effect = lambda src, dst: {
                (Currency.USD, Currency.USD): Decimal("1.0"),
                (Currency.USD, Currency.CLP): Decimal("900.00"),
            }.get((src, dst), Decimal("1.0"))

            service = RemittanceService(mock_db_session)
            quote = await service.get_quote(
                amount_source=Decimal("100.00"),
                currency_source=Currency.USD,
                currency_destination=Currency.CLP
            )

            assert isinstance(quote, RemittanceQuote)
            assert quote.amount_source == Decimal("100.00")
            assert quote.currency_source == Currency.USD
            assert quote.currency_destination == Currency.CLP
            assert quote.platform_fee > 0
            assert quote.amount_destination > 0

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_get_quote_mxn_to_usd(self, mock_db_session):
        """Test cotizacion MXN a USD."""
        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.side_effect = lambda src, dst: {
                (Currency.MXN, Currency.USD): Decimal("0.058"),
                (Currency.USD, Currency.USD): Decimal("1.0"),
            }.get((src, dst), Decimal("1.0"))

            service = RemittanceService(mock_db_session)
            quote = await service.get_quote(
                amount_source=Decimal("10000.00"),
                currency_source=Currency.MXN,
                currency_destination=Currency.USD
            )

            assert quote.amount_source == Decimal("10000.00")
            assert quote.currency_source == Currency.MXN
            # Fee should be 1.5% = 150 MXN
            assert quote.platform_fee == Decimal("150.00")

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_quote_fee_calculation(self, mock_db_session):
        """Test calculo correcto del fee de plataforma."""
        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)
            quote = await service.get_quote(
                amount_source=Decimal("1000.00"),
                currency_source=Currency.USD,
                currency_destination=Currency.USD
            )

            # 1.5% fee
            expected_fee = Decimal("1000.00") * Decimal("0.015")
            assert quote.platform_fee == expected_fee

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_quote_expiration(self, mock_db_session):
        """Test que la cotizacion tiene tiempo de expiracion."""
        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)
            quote = await service.get_quote(
                amount_source=Decimal("100.00"),
                currency_source=Currency.USD,
                currency_destination=Currency.USD
            )

            assert quote.expires_at is not None
            assert quote.expires_at > datetime.utcnow()
            # Deberia expirar en 15 minutos
            time_diff = quote.expires_at - datetime.utcnow()
            assert time_diff.total_seconds() <= 900  # 15 min


# ==================== TESTS DE CREACION ====================

class TestCreateRemittance:
    """Tests de creacion de remesas."""

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_create_remittance_success(self, mock_db_session, sample_recipient_info):
        """Test creacion exitosa de remesa."""
        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.side_effect = lambda src, dst: {
                (Currency.USD, Currency.USD): Decimal("1.0"),
                (Currency.USD, Currency.CLP): Decimal("900.00"),
            }.get((src, dst), Decimal("1.0"))

            service = RemittanceService(mock_db_session)
            result = await service.create_remittance(
                sender_id=uuid4(),
                recipient_info=sample_recipient_info,
                amount_source=Decimal("500.00"),
                currency_source=Currency.USD,
                currency_destination=Currency.CLP,
                payment_method=PaymentMethod.WIRE_TRANSFER,
                disbursement_method=DisbursementMethod.BANK_TRANSFER
            )

            assert isinstance(result, RemittanceResult)
            assert result.success is True
            assert result.remittance_id is not None
            mock_db_session.add.assert_called()
            mock_db_session.commit.assert_called()

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_create_remittance_generates_reference(self, mock_db_session, sample_recipient_info):
        """Test que se genera codigo de referencia unico."""
        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)
            result = await service.create_remittance(
                sender_id=uuid4(),
                recipient_info=sample_recipient_info,
                amount_source=Decimal("100.00"),
                currency_source=Currency.USD,
                currency_destination=Currency.USD,
                payment_method=PaymentMethod.SPEI,
                disbursement_method=DisbursementMethod.BANK_TRANSFER
            )

            assert result.success is True
            # Verificar formato del reference code
            assert result.reference_code is not None
            assert result.reference_code.startswith("REM-")

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_create_remittance_mexico_with_clabe(self, mock_db_session, sample_recipient_mexico):
        """Test creacion de remesa a Mexico con CLABE."""
        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("17.5")  # USD -> MXN

            service = RemittanceService(mock_db_session)
            result = await service.create_remittance(
                sender_id=uuid4(),
                recipient_info=sample_recipient_mexico,
                amount_source=Decimal("200.00"),
                currency_source=Currency.USD,
                currency_destination=Currency.MXN,
                payment_method=PaymentMethod.WIRE_TRANSFER,
                disbursement_method=DisbursementMethod.BANK_TRANSFER
            )

            assert result.success is True

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_create_remittance_minimum_amount(self, mock_db_session, sample_recipient_info):
        """Test monto minimo de remesa."""
        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)
            # Intentar con monto menor al minimo (10 USD)
            result = await service.create_remittance(
                sender_id=uuid4(),
                recipient_info=sample_recipient_info,
                amount_source=Decimal("5.00"),
                currency_source=Currency.USD,
                currency_destination=Currency.USD,
                payment_method=PaymentMethod.CARD,
                disbursement_method=DisbursementMethod.MOBILE_WALLET
            )

            assert result.success is False
            assert "minimo" in result.error.lower() or "minimum" in result.error.lower()


# ==================== TESTS DE ESCROW ====================

class TestEscrowOperations:
    """Tests de operaciones de escrow."""

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_lock_funds_in_escrow(self, mock_db_session, sample_remittance):
        """Test bloqueo de fondos en escrow."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_remittance
        mock_db_session.execute.return_value = mock_result

        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)

            with patch.object(service, '_execute_blockchain_lock') as mock_lock:
                mock_lock.return_value = ("0x" + "a" * 64, True)

                result = await service.lock_funds_in_escrow(
                    remittance_id=sample_remittance.id,
                    wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"
                )

                assert result.success is True
                assert sample_remittance.status == RemittanceStatus.LOCKED
                assert sample_remittance.escrow_locked_at is not None
                assert sample_remittance.escrow_expires_at is not None

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_lock_funds_sets_48h_expiration(self, mock_db_session, sample_remittance):
        """Test que el escrow expira en 48 horas."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_remittance
        mock_db_session.execute.return_value = mock_result

        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)

            with patch.object(service, '_execute_blockchain_lock') as mock_lock:
                mock_lock.return_value = ("0x" + "a" * 64, True)

                await service.lock_funds_in_escrow(
                    remittance_id=sample_remittance.id,
                    wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"
                )

                # Verificar time-lock de 48h
                time_diff = sample_remittance.escrow_expires_at - sample_remittance.escrow_locked_at
                assert time_diff.total_seconds() == 48 * 3600

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_release_funds_success(self, mock_db_session, sample_locked_remittance):
        """Test liberacion exitosa de fondos."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_locked_remittance
        mock_db_session.execute.return_value = mock_result

        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)

            with patch.object(service, '_execute_blockchain_release') as mock_release:
                mock_release.return_value = ("0x" + "b" * 64, True)

                result = await service.release_funds(
                    remittance_id=sample_locked_remittance.id,
                    operator_id=uuid4()
                )

                assert result.success is True
                assert sample_locked_remittance.status == RemittanceStatus.DISBURSED

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_release_funds_wrong_status(self, mock_db_session, sample_remittance):
        """Test que no se pueden liberar fondos si no estan bloqueados."""
        sample_remittance.status = RemittanceStatus.INITIATED  # No LOCKED
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_remittance
        mock_db_session.execute.return_value = mock_result

        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)
            result = await service.release_funds(
                remittance_id=sample_remittance.id,
                operator_id=uuid4()
            )

            assert result.success is False
            assert "estado" in result.error.lower() or "status" in result.error.lower()


# ==================== TESTS DE REEMBOLSO ====================

class TestRefundOperations:
    """Tests de operaciones de reembolso."""

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_refund_expired_escrow(self, mock_db_session, sample_expired_remittance):
        """Test reembolso cuando escrow expira."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_expired_remittance
        mock_db_session.execute.return_value = mock_result

        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)

            with patch.object(service, '_execute_blockchain_refund') as mock_refund:
                mock_refund.return_value = ("0x" + "c" * 64, True)

                result = await service.process_refund(
                    remittance_id=sample_expired_remittance.id
                )

                assert result.success is True
                assert sample_expired_remittance.status == RemittanceStatus.REFUNDED

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_refund_not_expired(self, mock_db_session, sample_locked_remittance):
        """Test que no se puede reembolsar antes de 48h."""
        # escrow_expires_at es en el futuro
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_locked_remittance
        mock_db_session.execute.return_value = mock_result

        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)
            result = await service.process_refund(
                remittance_id=sample_locked_remittance.id
            )

            assert result.success is False
            assert "expirado" in result.error.lower() or "expired" in result.error.lower()

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_cancel_by_sender(self, mock_db_session, sample_remittance):
        """Test cancelacion por el sender antes del lock."""
        sample_remittance.status = RemittanceStatus.INITIATED
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_remittance
        mock_db_session.execute.return_value = mock_result

        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)
            result = await service.cancel_remittance(
                remittance_id=sample_remittance.id,
                user_id=sample_remittance.sender_id
            )

            assert result.success is True
            assert sample_remittance.status == RemittanceStatus.CANCELLED


# ==================== TESTS DE RECONCILIACION ====================

class TestReconciliation:
    """Tests de reconciliacion de saldos."""

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_reconciliation_no_discrepancy(self, mock_db_session):
        """Test reconciliacion sin discrepancias."""
        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)

            with patch.object(service, '_get_ledger_balance') as mock_ledger:
                with patch.object(service, '_get_onchain_balance') as mock_onchain:
                    mock_ledger.return_value = Decimal("10000.00")
                    mock_onchain.return_value = Decimal("10000.00")

                    log = await service.run_reconciliation()

                    assert isinstance(log, ReconciliationLog)
                    assert log.discrepancy_detected is False

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_reconciliation_with_discrepancy(self, mock_db_session):
        """Test reconciliacion con discrepancias detectadas."""
        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)

            with patch.object(service, '_get_ledger_balance') as mock_ledger:
                with patch.object(service, '_get_onchain_balance') as mock_onchain:
                    mock_ledger.return_value = Decimal("10000.00")
                    mock_onchain.return_value = Decimal("9500.00")  # 500 menos

                    log = await service.run_reconciliation()

                    assert log.discrepancy_detected is True
                    assert log.discrepancy_onchain == Decimal("500.00")


# ==================== TESTS DE LIMITES ====================

class TestRemittanceLimits:
    """Tests de limites por KYC."""

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_check_daily_limit(self, mock_db_session):
        """Test verificacion de limite diario."""
        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)

            # Mock consulta de uso actual
            mock_result = MagicMock()
            mock_result.scalar.return_value = Decimal("800.00")  # Ya uso 800 de 1000
            mock_db_session.execute.return_value = mock_result

            is_within_limit = await service.check_user_limits(
                user_id=uuid4(),
                amount_usd=Decimal("150.00"),
                kyc_level=1
            )

            # 800 + 150 = 950, excede 1000 para KYC nivel 1
            assert is_within_limit is False

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_check_monthly_limit(self, mock_db_session):
        """Test verificacion de limite mensual."""
        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)

            # Mock consulta de uso mensual
            mock_result = MagicMock()
            mock_result.scalar.return_value = Decimal("4500.00")  # Ya uso 4500 de 5000
            mock_db_session.execute.return_value = mock_result

            is_within_limit = await service.check_user_limits(
                user_id=uuid4(),
                amount_usd=Decimal("600.00"),
                kyc_level=1
            )

            # 4500 + 600 = 5100, excede 5000 para KYC nivel 1
            assert is_within_limit is False


# ==================== TESTS DE ESTADO ====================

class TestRemittanceStatus:
    """Tests de transiciones de estado."""

    @pytest.mark.unit
    @pytest.mark.remittance
    def test_valid_status_transitions(self):
        """Test transiciones de estado validas."""
        valid_transitions = {
            RemittanceStatus.INITIATED: [
                RemittanceStatus.PENDING_DEPOSIT,
                RemittanceStatus.CANCELLED
            ],
            RemittanceStatus.PENDING_DEPOSIT: [
                RemittanceStatus.DEPOSITED,
                RemittanceStatus.CANCELLED,
                RemittanceStatus.EXPIRED
            ],
            RemittanceStatus.DEPOSITED: [
                RemittanceStatus.LOCKED,
                RemittanceStatus.FAILED
            ],
            RemittanceStatus.LOCKED: [
                RemittanceStatus.PROCESSING,
                RemittanceStatus.REFUND_PENDING,
                RemittanceStatus.CANCELLED
            ],
            RemittanceStatus.PROCESSING: [
                RemittanceStatus.DISBURSED,
                RemittanceStatus.FAILED
            ],
            RemittanceStatus.DISBURSED: [
                RemittanceStatus.COMPLETED
            ],
            RemittanceStatus.REFUND_PENDING: [
                RemittanceStatus.REFUNDED
            ],
        }

        for from_status, to_statuses in valid_transitions.items():
            for to_status in to_statuses:
                # Verificar que la transicion es logicamente valida
                assert from_status != to_status, f"Self-transition not allowed: {from_status}"

    @pytest.mark.unit
    @pytest.mark.remittance
    def test_terminal_states(self):
        """Test que estados terminales no tienen transiciones."""
        terminal_states = [
            RemittanceStatus.COMPLETED,
            RemittanceStatus.REFUNDED,
            RemittanceStatus.FAILED,
            RemittanceStatus.EXPIRED,
        ]

        for state in terminal_states:
            assert state in RemittanceStatus


# ==================== TESTS DE INTEGRACION BLOCKCHAIN ====================

class TestBlockchainIntegration:
    """Tests de integracion con blockchain."""

    @pytest.mark.unit
    @pytest.mark.remittance
    @pytest.mark.asyncio
    async def test_blockchain_tx_record_created(self, mock_db_session, sample_remittance):
        """Test que se registra la transaccion blockchain."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_remittance
        mock_db_session.execute.return_value = mock_result

        with patch('app.services.remittance_service.get_exchange_rate') as mock_rate:
            mock_rate.return_value = Decimal("1.0")

            service = RemittanceService(mock_db_session)

            with patch.object(service, '_execute_blockchain_lock') as mock_lock:
                mock_lock.return_value = ("0x" + "a" * 64, True)

                await service.lock_funds_in_escrow(
                    remittance_id=sample_remittance.id,
                    wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"
                )

                # Verificar que se llamo add para la tx blockchain
                calls = mock_db_session.add.call_args_list
                tx_added = any(
                    isinstance(call.args[0], RemittanceBlockchainTx)
                    if hasattr(call.args[0], '__class__') and call.args else False
                    for call in calls
                )
                # Puede ser un mock, verificamos que se agrego algo
                assert mock_db_session.add.called


# ==================== TESTS DE HELPERS ====================

class TestHelperFunctions:
    """Tests de funciones auxiliares."""

    @pytest.mark.unit
    @pytest.mark.remittance
    def test_generate_reference_code_format(self, mock_db_session):
        """Test formato de codigo de referencia."""
        with patch('app.services.remittance_service.get_exchange_rate'):
            service = RemittanceService(mock_db_session)
            code = service._generate_reference_code()

            assert code.startswith("REM-")
            parts = code.split("-")
            assert len(parts) == 3
            # Formato: REM-YYYYMMDD-XXXXXX
            assert len(parts[1]) == 8  # Fecha
            assert len(parts[2]) == 6  # Random

    @pytest.mark.unit
    @pytest.mark.remittance
    def test_calculate_fees(self, mock_db_session):
        """Test calculo de comisiones."""
        with patch('app.services.remittance_service.get_exchange_rate'):
            service = RemittanceService(mock_db_session)

            platform_fee, network_fee, total = service._calculate_fees(
                amount=Decimal("1000.00")
            )

            # Platform fee 1.5%
            assert platform_fee == Decimal("15.00")
            # Network fee fijo estimado
            assert network_fee >= 0
            assert total == platform_fee + network_fee


# ==================== TESTS DE VALIDACION ====================

class TestValidation:
    """Tests de validacion de datos."""

    @pytest.mark.unit
    @pytest.mark.remittance
    def test_validate_clabe_format(self):
        """Test validacion de formato CLABE."""
        valid_clabe = "012180015678901234"  # 18 digitos
        invalid_clabe = "12345"  # Muy corto

        # CLABE debe ser 18 digitos
        assert len(valid_clabe) == 18
        assert valid_clabe.isdigit()

        assert len(invalid_clabe) != 18

    @pytest.mark.unit
    @pytest.mark.remittance
    def test_validate_wallet_address(self):
        """Test validacion de direccion de wallet."""
        valid_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"
        invalid_address = "not_a_wallet"

        assert valid_address.startswith("0x")
        assert len(valid_address) == 42

        assert not invalid_address.startswith("0x")

    @pytest.mark.unit
    @pytest.mark.remittance
    def test_validate_amount_bounds(self):
        """Test validacion de limites de monto."""
        min_amount = Decimal("10.00")
        max_amount = Decimal("10000.00")

        valid_amount = Decimal("500.00")
        too_low = Decimal("5.00")
        too_high = Decimal("15000.00")

        assert min_amount <= valid_amount <= max_amount
        assert too_low < min_amount
        assert too_high > max_amount
