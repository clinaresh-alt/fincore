"""
Tests de integracion para el modulo de Remesas.

Estos tests validan la integracion entre:
- RemittanceService (logica de negocio)
- BlockchainService (interaccion con smart contracts)
- Modelos de datos (Remittance, RemittanceBlockchainTx)

Nota: Los tests usan mocks para evitar dependencias de
PostgreSQL (JSONB) y conexiones reales a blockchain.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4

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
from app.models.user import User, UserRole
from app.models.compliance import KYCProfile, KYCLevel
from app.services.remittance_service import (
    RemittanceService,
    RemittanceQuote,
    RemittanceResult,
)
from app.services.blockchain_service import TransactionResult


# ==================== FIXTURES ====================

@pytest.fixture
def mock_db():
    """Mock de sesion de base de datos."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.flush = MagicMock()
    db.rollback = MagicMock()
    db.query = MagicMock()
    return db


@pytest.fixture
def mock_blockchain_service():
    """Mock del servicio blockchain."""
    service = MagicMock()
    service.execute_contract_function = MagicMock(return_value=TransactionResult(
        success=True,
        tx_hash="0x" + "a" * 64,
        block_number=12345678,
        gas_used=150000
    ))
    service.call_contract_function = MagicMock(return_value=1)
    return service


@pytest.fixture
def sample_user():
    """Usuario de prueba."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "test@fincore.mx"
    user.rol = UserRole.INVERSIONISTA
    user.is_active = True
    return user


@pytest.fixture
def sample_kyc_profile(sample_user):
    """Perfil KYC verificado."""
    kyc = MagicMock(spec=KYCProfile)
    kyc.user_id = sample_user.id
    kyc.current_level = KYCLevel.LEVEL_2
    kyc.is_verified = True
    return kyc


@pytest.fixture
def sample_recipient_info():
    """Datos de beneficiario."""
    return {
        "name": "Juan Perez Garcia",
        "bank_name": "BBVA Mexico",
        "account_number": "1234567890",
        "account_type": "checking",
        "clabe": "012180015678901234",
        "phone": "+525512345678",
        "email": "juan.perez@email.com",
        "country": "MX"
    }


@pytest.fixture
def sample_remittance(sample_user):
    """Remesa de prueba en estado INITIATED."""
    remittance = MagicMock(spec=Remittance)
    remittance.id = uuid4()
    remittance.reference_code = "FRC-TEST1234"
    remittance.sender_id = sample_user.id
    remittance.recipient_info = {"name": "Juan Perez", "bank_name": "BBVA"}
    remittance.amount_fiat_source = Decimal("500.00")
    remittance.currency_source = Currency.USD
    remittance.amount_fiat_destination = Decimal("8750.00")
    remittance.currency_destination = Currency.MXN
    remittance.amount_stablecoin = Decimal("492.50")
    remittance.stablecoin = Stablecoin.USDC
    remittance.exchange_rate_source_usd = Decimal("1.0")
    remittance.exchange_rate_usd_destination = Decimal("17.5")
    remittance.platform_fee = Decimal("7.50")
    remittance.network_fee = Decimal("0.50")
    remittance.total_fees = Decimal("8.00")
    remittance.status = RemittanceStatus.INITIATED
    remittance.payment_method = PaymentMethod.WIRE_TRANSFER
    remittance.disbursement_method = DisbursementMethod.BANK_TRANSFER
    remittance.escrow_locked_at = None
    remittance.escrow_expires_at = None
    remittance.created_at = datetime.utcnow()
    return remittance


@pytest.fixture
def deposited_remittance(sample_remittance):
    """Remesa en estado DEPOSITED."""
    sample_remittance.status = RemittanceStatus.DEPOSITED
    return sample_remittance


@pytest.fixture
def locked_remittance(sample_remittance):
    """Remesa en estado LOCKED."""
    sample_remittance.status = RemittanceStatus.LOCKED
    sample_remittance.escrow_locked_at = datetime.utcnow()
    sample_remittance.escrow_expires_at = datetime.utcnow() + timedelta(hours=48)
    return sample_remittance


@pytest.fixture
def expired_remittance(sample_remittance):
    """Remesa expirada (escrow vencido)."""
    sample_remittance.status = RemittanceStatus.LOCKED
    sample_remittance.escrow_locked_at = datetime.utcnow() - timedelta(hours=50)
    sample_remittance.escrow_expires_at = datetime.utcnow() - timedelta(hours=2)
    return sample_remittance


# ==================== TESTS DE COTIZACION ====================

class TestQuoteIntegration:
    """Tests de cotizacion de remesas."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_quote_usd_to_mxn(self, mock_db):
        """Test cotizacion USD a MXN."""
        service = RemittanceService(mock_db)

        quote = await service.get_quote(
            amount_source=Decimal("500.00"),
            currency_source=Currency.USD,
            currency_destination=Currency.MXN
        )

        assert isinstance(quote, RemittanceQuote)
        assert quote.amount_source == Decimal("500.00")
        assert quote.currency_source == Currency.USD
        assert quote.currency_destination == Currency.MXN
        assert quote.amount_destination > 0
        assert quote.platform_fee > 0
        assert quote.quote_id is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_quote_mxn_to_usd(self, mock_db):
        """Test cotizacion MXN a USD."""
        service = RemittanceService(mock_db)

        quote = await service.get_quote(
            amount_source=Decimal("10000.00"),
            currency_source=Currency.MXN,
            currency_destination=Currency.USD
        )

        assert quote.amount_source == Decimal("10000.00")
        assert quote.currency_source == Currency.MXN
        # Fee es 1.5% de 10000 = 150 MXN
        assert quote.platform_fee == Decimal("150.00")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_quote_expiration(self, mock_db):
        """Test que la cotizacion tiene expiracion de 15 minutos."""
        service = RemittanceService(mock_db)

        quote = await service.get_quote(
            amount_source=Decimal("100.00"),
            currency_source=Currency.USD,
            currency_destination=Currency.USD
        )

        assert quote.quote_expires_at is not None
        assert quote.quote_expires_at > datetime.utcnow()
        # Debe expirar en ~15 minutos
        time_diff = quote.quote_expires_at - datetime.utcnow()
        assert time_diff.total_seconds() <= 900  # 15 min


# ==================== TESTS DE CREACION ====================

class TestCreateRemittanceIntegration:
    """Tests de creacion de remesas."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_remittance_success(
        self, mock_db, sample_user, sample_kyc_profile, sample_recipient_info
    ):
        """Test creacion exitosa de remesa."""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_user,  # User query
            sample_kyc_profile,  # KYC query
            None,  # RemittanceLimit query
        ]

        service = RemittanceService(mock_db)

        result = await service.create_remittance(
            sender_id=str(sample_user.id),
            recipient_info=sample_recipient_info,
            amount_source=Decimal("500.00"),
            currency_source=Currency.USD,
            currency_destination=Currency.MXN,
            payment_method=PaymentMethod.WIRE_TRANSFER,
            disbursement_method=DisbursementMethod.BANK_TRANSFER,
        )

        assert isinstance(result, RemittanceResult)
        assert result.success is True
        assert result.reference_code is not None
        assert result.reference_code.startswith("FRC-")
        assert result.status == RemittanceStatus.INITIATED
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_remittance_user_not_found(self, mock_db, sample_recipient_info):
        """Test creacion falla si usuario no existe."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = RemittanceService(mock_db)

        result = await service.create_remittance(
            sender_id=str(uuid4()),
            recipient_info=sample_recipient_info,
            amount_source=Decimal("500.00"),
            currency_source=Currency.USD,
            currency_destination=Currency.MXN,
            payment_method=PaymentMethod.WIRE_TRANSFER,
            disbursement_method=DisbursementMethod.BANK_TRANSFER,
        )

        assert result.success is False
        assert "no encontrado" in result.error.lower()


# ==================== TESTS DE LOCK ====================

class TestLockFundsIntegration:
    """Tests de bloqueo de fondos en escrow."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_lock_funds_success(
        self, mock_db, deposited_remittance, mock_blockchain_service
    ):
        """Test bloqueo exitoso de fondos."""
        mock_db.query.return_value.filter.return_value.first.return_value = deposited_remittance

        service = RemittanceService(mock_db)
        service.blockchain_service = mock_blockchain_service

        result = await service.lock_funds_in_escrow(
            remittance_id=str(deposited_remittance.id),
            wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"
        )

        assert result.success is True
        assert result.status == RemittanceStatus.LOCKED
        assert result.tx_hash is not None
        assert deposited_remittance.status == RemittanceStatus.LOCKED
        assert deposited_remittance.escrow_locked_at is not None
        assert deposited_remittance.escrow_expires_at is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_lock_funds_wrong_status(self, mock_db, sample_remittance):
        """Test que no se puede bloquear remesa en estado incorrecto."""
        # Status INITIATED, no DEPOSITED
        mock_db.query.return_value.filter.return_value.first.return_value = sample_remittance

        service = RemittanceService(mock_db)

        result = await service.lock_funds_in_escrow(
            remittance_id=str(sample_remittance.id),
            wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"
        )

        assert result.success is False
        assert "Estado invalido" in result.error

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_lock_funds_not_found(self, mock_db):
        """Test bloqueo falla si remesa no existe."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = RemittanceService(mock_db)

        result = await service.lock_funds_in_escrow(
            remittance_id=str(uuid4()),
            wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"
        )

        assert result.success is False
        assert "no encontrada" in result.error.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_lock_funds_blockchain_error(
        self, mock_db, deposited_remittance, mock_blockchain_service
    ):
        """Test manejo de error de blockchain durante lock."""
        mock_db.query.return_value.filter.return_value.first.return_value = deposited_remittance
        mock_blockchain_service.execute_contract_function.return_value = TransactionResult(
            success=False,
            error="Insufficient balance"
        )

        service = RemittanceService(mock_db)
        service.blockchain_service = mock_blockchain_service

        result = await service.lock_funds_in_escrow(
            remittance_id=str(deposited_remittance.id),
            wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"
        )

        assert result.success is False
        assert "blockchain" in result.error.lower()


# ==================== TESTS DE RELEASE ====================

class TestReleaseFundsIntegration:
    """Tests de liberacion de fondos."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_release_funds_success(
        self, mock_db, locked_remittance, mock_blockchain_service
    ):
        """Test liberacion exitosa de fondos."""
        mock_db.query.return_value.filter.return_value.first.return_value = locked_remittance

        service = RemittanceService(mock_db)
        service.blockchain_service = mock_blockchain_service

        result = await service.release_funds(
            remittance_id=str(locked_remittance.id),
            operator_id=str(uuid4())
        )

        assert result.success is True
        assert result.status == RemittanceStatus.DISBURSED
        assert result.tx_hash is not None
        assert locked_remittance.status == RemittanceStatus.DISBURSED
        assert locked_remittance.completed_at is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_release_funds_wrong_status(self, mock_db, sample_remittance):
        """Test que no se puede liberar remesa no bloqueada."""
        # Status INITIATED, no LOCKED
        mock_db.query.return_value.filter.return_value.first.return_value = sample_remittance

        service = RemittanceService(mock_db)

        result = await service.release_funds(
            remittance_id=str(sample_remittance.id),
            operator_id=str(uuid4())
        )

        assert result.success is False
        assert "Estado invalido" in result.error

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_release_funds_onchain_not_found(
        self, mock_db, locked_remittance, mock_blockchain_service
    ):
        """Test liberacion falla si remesa no existe on-chain."""
        mock_db.query.return_value.filter.return_value.first.return_value = locked_remittance
        mock_blockchain_service.call_contract_function.return_value = 0  # No existe

        service = RemittanceService(mock_db)
        service.blockchain_service = mock_blockchain_service

        result = await service.release_funds(
            remittance_id=str(locked_remittance.id),
            operator_id=str(uuid4())
        )

        assert result.success is False
        assert "blockchain" in result.error.lower()


# ==================== TESTS DE REFUND ====================

class TestRefundIntegration:
    """Tests de reembolso."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_refund_expired_success(
        self, mock_db, expired_remittance, mock_blockchain_service
    ):
        """Test reembolso exitoso de escrow expirado."""
        mock_db.query.return_value.filter.return_value.first.return_value = expired_remittance
        mock_blockchain_service.call_contract_function.return_value = True  # canRefund

        service = RemittanceService(mock_db)
        service.blockchain_service = mock_blockchain_service

        result = await service.process_refund(
            remittance_id=str(expired_remittance.id)
        )

        assert result.success is True
        assert result.status == RemittanceStatus.REFUNDED
        assert result.tx_hash is not None
        assert expired_remittance.status == RemittanceStatus.REFUNDED
        assert expired_remittance.completed_at is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_refund_not_expired(self, mock_db, locked_remittance):
        """Test que no se puede reembolsar antes de expiracion."""
        mock_db.query.return_value.filter.return_value.first.return_value = locked_remittance

        service = RemittanceService(mock_db)

        result = await service.process_refund(
            remittance_id=str(locked_remittance.id)
        )

        assert result.success is False
        assert "expirado" in result.error.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_refund_wrong_status(self, mock_db, sample_remittance):
        """Test que no se puede reembolsar remesa no bloqueada."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_remittance

        service = RemittanceService(mock_db)

        result = await service.process_refund(
            remittance_id=str(sample_remittance.id)
        )

        assert result.success is False
        assert "Estado invalido" in result.error


# ==================== TESTS DE CONSULTAS ====================

class TestQueriesIntegration:
    """Tests de consultas de remesas."""

    @pytest.mark.integration
    def test_get_remittance_by_id(self, mock_db, sample_remittance):
        """Test obtener remesa por ID."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_remittance

        service = RemittanceService(mock_db)
        result = service.get_remittance(str(sample_remittance.id))

        assert result is not None
        assert result.id == sample_remittance.id

    @pytest.mark.integration
    def test_get_remittance_by_reference(self, mock_db, sample_remittance):
        """Test obtener remesa por codigo de referencia."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_remittance

        service = RemittanceService(mock_db)
        result = service.get_remittance_by_reference("FRC-TEST1234")

        assert result is not None
        assert result.reference_code == "FRC-TEST1234"

    @pytest.mark.integration
    def test_get_user_remittances(self, mock_db, sample_user):
        """Test listar remesas de usuario."""
        remittances = [MagicMock() for _ in range(5)]
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = remittances

        service = RemittanceService(mock_db)
        result = service.get_user_remittances(str(sample_user.id))

        assert len(result) == 5

    @pytest.mark.integration
    def test_get_pending_refunds(self, mock_db, expired_remittance):
        """Test obtener remesas pendientes de reembolso."""
        mock_db.query.return_value.filter.return_value.all.return_value = [expired_remittance]

        service = RemittanceService(mock_db)
        result = service.get_pending_refunds()

        assert len(result) == 1


# ==================== TESTS DE CONCILIACION ====================

class TestReconciliationIntegration:
    """Tests de conciliacion de saldos."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reconciliation_no_discrepancy(
        self, mock_db, mock_blockchain_service
    ):
        """Test conciliacion sin discrepancias."""
        mock_db.query.return_value.filter.return_value.scalar.return_value = Decimal("10000.00")
        # getTotals devuelve: (locked, released, refunded, fees)
        mock_blockchain_service.call_contract_function.return_value = [
            10000000000,  # 10000 USDC (6 decimals)
            5000000000,   # 5000 released
            1000000000,   # 1000 refunded
            150000000     # 150 fees
        ]

        service = RemittanceService(mock_db)
        service.blockchain_service = mock_blockchain_service

        log = await service.run_reconciliation()

        assert isinstance(log, ReconciliationLog)
        assert log.discrepancy_detected is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reconciliation_with_discrepancy(
        self, mock_db, mock_blockchain_service
    ):
        """Test conciliacion con discrepancia detectada."""
        mock_db.query.return_value.filter.return_value.scalar.return_value = Decimal("10000.00")
        # getTotals devuelve menos del esperado
        mock_blockchain_service.call_contract_function.return_value = [
            9500000000,  # 9500 USDC - 500 menos
            5000000000,
            1000000000,
            150000000
        ]

        service = RemittanceService(mock_db)
        service.blockchain_service = mock_blockchain_service

        log = await service.run_reconciliation()

        assert log.discrepancy_detected is True
        assert log.discrepancy_onchain > Decimal("0")


# ==================== TESTS DE FLUJO COMPLETO ====================

class TestFullFlowIntegration:
    """Tests del flujo completo de una remesa."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_remittance_flow(
        self, mock_db, sample_user, mock_blockchain_service
    ):
        """Test flujo completo: lock -> release."""
        # Simular remesa en estado DEPOSITED
        deposited = MagicMock(spec=Remittance)
        deposited.id = uuid4()
        deposited.reference_code = "FRC-FLOW0001"
        deposited.status = RemittanceStatus.DEPOSITED
        deposited.amount_stablecoin = Decimal("492.50")
        deposited.stablecoin = Stablecoin.USDC
        deposited.escrow_locked_at = None
        deposited.escrow_expires_at = None

        mock_db.query.return_value.filter.return_value.first.return_value = deposited

        service = RemittanceService(mock_db)
        service.blockchain_service = mock_blockchain_service

        # 1. Lock en escrow
        lock_result = await service.lock_funds_in_escrow(
            remittance_id=str(deposited.id),
            wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"
        )
        assert lock_result.success is True
        assert lock_result.status == RemittanceStatus.LOCKED
        assert lock_result.tx_hash is not None

        # Simular remesa bloqueada
        locked = MagicMock(spec=Remittance)
        locked.id = deposited.id
        locked.reference_code = deposited.reference_code
        locked.status = RemittanceStatus.LOCKED
        locked.escrow_locked_at = datetime.utcnow()
        locked.escrow_expires_at = datetime.utcnow() + timedelta(hours=48)
        locked.completed_at = None

        mock_db.query.return_value.filter.return_value.first.return_value = locked
        mock_blockchain_service.call_contract_function.return_value = 1  # onchain ID

        # 2. Release
        release_result = await service.release_funds(
            remittance_id=str(locked.id),
            operator_id=str(uuid4())
        )
        assert release_result.success is True
        assert release_result.status == RemittanceStatus.DISBURSED
        assert release_result.tx_hash is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_remittance_refund_flow(
        self, mock_db, sample_user, mock_blockchain_service
    ):
        """Test flujo de reembolso: remesa expirada -> refund."""
        # Simular remesa expirada (48h despues del lock)
        expired = MagicMock(spec=Remittance)
        expired.id = uuid4()
        expired.reference_code = "FRC-EXPIRED1"
        expired.status = RemittanceStatus.LOCKED
        expired.escrow_locked_at = datetime.utcnow() - timedelta(hours=50)
        expired.escrow_expires_at = datetime.utcnow() - timedelta(hours=2)
        expired.completed_at = None

        mock_db.query.return_value.filter.return_value.first.return_value = expired
        mock_blockchain_service.call_contract_function.return_value = True  # canRefund

        service = RemittanceService(mock_db)
        service.blockchain_service = mock_blockchain_service

        # Refund
        refund_result = await service.process_refund(
            remittance_id=str(expired.id)
        )
        assert refund_result.success is True
        assert refund_result.status == RemittanceStatus.REFUNDED
        assert refund_result.tx_hash is not None


# ==================== TESTS DE HELPERS ====================

class TestHelperFunctions:
    """Tests de funciones auxiliares."""

    @pytest.mark.integration
    def test_reference_to_bytes32(self, mock_db):
        """Test conversion de referencia a bytes32."""
        service = RemittanceService(mock_db)

        result = service._reference_to_bytes32("FRC-TEST1234")

        assert result is not None
        assert len(result) == 32

    @pytest.mark.integration
    def test_amount_to_wei(self, mock_db):
        """Test conversion de monto a wei."""
        service = RemittanceService(mock_db)

        # 100 USDC (6 decimals) = 100000000 wei
        result = service._amount_to_wei(Decimal("100.00"), 6)

        assert result == 100000000

    @pytest.mark.integration
    def test_wei_to_amount(self, mock_db):
        """Test conversion de wei a monto."""
        service = RemittanceService(mock_db)

        # 100000000 wei (6 decimals) = 100 USDC
        result = service._wei_to_amount(100000000, 6)

        assert result == Decimal("100")

    @pytest.mark.integration
    def test_get_stablecoin_address(self, mock_db):
        """Test obtencion de direccion de stablecoin."""
        service = RemittanceService(mock_db, network="polygon")

        address = service._get_stablecoin_address(Stablecoin.USDC)

        assert address is not None
        assert address.startswith("0x")
        assert len(address) == 42
