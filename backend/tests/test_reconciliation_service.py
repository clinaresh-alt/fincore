"""
Tests para el Servicio de Reconciliacion.

Prueba el motor de reconciliacion entre Ledger y On-chain:
- Obtener totales de Ledger
- Obtener totales On-chain
- Detectar discrepancias
- Reconciliar remesas individuales
- Enviar alertas
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4

from app.models.remittance import (
    Remittance,
    RemittanceBlockchainTx,
    ReconciliationLog,
    RemittanceStatus,
    BlockchainRemittanceStatus,
    Stablecoin,
)
from app.services.reconciliation_service import (
    ReconciliationService,
    ReconciliationResult,
    TransactionReconciliation,
    BalanceSnapshot,
    DiscrepancyType,
    AlertSeverity,
    DISCREPANCY_THRESHOLD,
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
    db.query = MagicMock()
    return db


@pytest.fixture
def mock_blockchain_service():
    """Mock del servicio blockchain."""
    service = MagicMock()
    # getTotals retorna: (locked, released, refunded, fees) en wei
    service.call_contract_function = MagicMock(return_value=[
        10000000000,  # 10000 USDC locked
        5000000000,   # 5000 USDC released
        1000000000,   # 1000 USDC refunded
        150000000,    # 150 USDC fees
    ])
    return service


@pytest.fixture
def sample_remittance():
    """Remesa de prueba."""
    remittance = MagicMock(spec=Remittance)
    remittance.id = uuid4()
    remittance.reference_code = "FRC-TEST1234"
    remittance.status = RemittanceStatus.LOCKED
    remittance.amount_stablecoin = Decimal("500.00")
    remittance.stablecoin = Stablecoin.USDC
    return remittance


@pytest.fixture
def sample_blockchain_tx():
    """Transaccion blockchain de prueba."""
    tx = MagicMock(spec=RemittanceBlockchainTx)
    tx.id = uuid4()
    tx.remittance_id = uuid4()
    tx.tx_hash = "0x" + "a" * 64
    tx.operation = "lock"
    tx.blockchain_status = BlockchainRemittanceStatus.SUBMITTED
    tx.created_at = datetime.utcnow() - timedelta(minutes=15)
    return tx


# ==================== TESTS DE TOTALES ====================

class TestGetLedgerTotals:
    """Tests de obtener totales del Ledger."""

    @pytest.mark.integration
    def test_get_ledger_totals_success(self, mock_db):
        """Test obtener totales del ledger."""
        # Mock query results
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [
            Decimal("10000.00"),  # locked
            Decimal("5000.00"),   # released
            Decimal("1000.00"),   # refunded
            Decimal("150.00"),    # fees
        ]

        service = ReconciliationService(mock_db)
        totals = service.get_ledger_totals()

        assert totals["locked"] == Decimal("10000.00")
        assert totals["released"] == Decimal("5000.00")
        assert totals["refunded"] == Decimal("1000.00")
        assert totals["fees"] == Decimal("150.00")

    @pytest.mark.integration
    def test_get_ledger_totals_empty(self, mock_db):
        """Test totales cuando no hay remesas."""
        mock_db.query.return_value.filter.return_value.scalar.return_value = None

        service = ReconciliationService(mock_db)
        totals = service.get_ledger_totals()

        assert totals["locked"] == Decimal("0")
        assert totals["released"] == Decimal("0")


class TestGetOnchainTotals:
    """Tests de obtener totales On-chain."""

    @pytest.mark.integration
    def test_get_onchain_totals_success(self, mock_db, mock_blockchain_service):
        """Test obtener totales on-chain."""
        service = ReconciliationService(mock_db)
        service.blockchain_service = mock_blockchain_service

        totals = service.get_onchain_totals()

        assert totals["locked"] == Decimal("10000")
        assert totals["released"] == Decimal("5000")
        assert totals["refunded"] == Decimal("1000")
        assert totals["fees"] == Decimal("150")

    @pytest.mark.integration
    def test_get_onchain_totals_invalid_response(self, mock_db, mock_blockchain_service):
        """Test manejo de respuesta invalida."""
        mock_blockchain_service.call_contract_function.return_value = None

        service = ReconciliationService(mock_db)
        service.blockchain_service = mock_blockchain_service

        totals = service.get_onchain_totals()

        assert totals["locked"] == Decimal("0")


# ==================== TESTS DE RECONCILIACION ====================

class TestFullReconciliation:
    """Tests de reconciliacion completa."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reconciliation_no_discrepancy(self, mock_db, mock_blockchain_service):
        """Test reconciliacion sin discrepancias."""
        # Configurar ledger para que coincida con on-chain
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [
            Decimal("10000.00"),  # locked
            Decimal("5000.00"),   # released
            Decimal("1000.00"),   # refunded
            Decimal("150.00"),    # fees
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = []  # No stuck txs

        service = ReconciliationService(mock_db)
        service.blockchain_service = mock_blockchain_service

        result = await service.run_full_reconciliation(stablecoin="USDC")

        assert result.success is True
        assert len(result.discrepancies) == 0
        assert result.balance_snapshot is not None
        mock_db.add.assert_called()  # Se creo log

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reconciliation_with_discrepancy(self, mock_db, mock_blockchain_service):
        """Test reconciliacion con discrepancia detectada."""
        # Ledger tiene mas que on-chain
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [
            Decimal("15000.00"),  # locked - 5000 mas que on-chain
            Decimal("5000.00"),
            Decimal("1000.00"),
            Decimal("150.00"),
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = []

        service = ReconciliationService(mock_db)
        service.blockchain_service = mock_blockchain_service

        result = await service.run_full_reconciliation(stablecoin="USDC")

        assert result.success is True
        assert len(result.discrepancies) > 0
        # Verificar que se detecto discrepancia en locked
        locked_disc = next(
            (d for d in result.discrepancies if d.get("field") == "locked"),
            None
        )
        assert locked_disc is not None
        assert locked_disc["difference"] in ("5000", "5000.00")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reconciliation_detects_stuck_transactions(
        self, mock_db, mock_blockchain_service, sample_blockchain_tx
    ):
        """Test que detecta transacciones atascadas."""
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [
            Decimal("10000.00"),
            Decimal("5000.00"),
            Decimal("1000.00"),
            Decimal("150.00"),
        ]
        # Retornar transaccion atascada
        mock_db.query.return_value.filter.return_value.all.return_value = [sample_blockchain_tx]

        service = ReconciliationService(mock_db)
        service.blockchain_service = mock_blockchain_service

        result = await service.run_full_reconciliation(stablecoin="USDC")

        assert result.success is True
        # Debe haber detectado la transaccion atascada
        stuck_disc = next(
            (d for d in result.discrepancies if d.get("type") == DiscrepancyType.STUCK_TX.value),
            None
        )
        assert stuck_disc is not None


# ==================== TESTS DE RECONCILIACION INDIVIDUAL ====================

class TestSingleRemittanceReconciliation:
    """Tests de reconciliacion de remesa individual."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reconcile_single_matched(self, mock_db, mock_blockchain_service, sample_remittance):
        """Test remesa que coincide."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_remittance

        # Mock on-chain data
        mock_blockchain_service.call_contract_function.side_effect = [
            1,  # getRemittanceByReference -> ID
            (
                b"ref",  # referenceId
                "0x123",  # sender
                "0x456",  # token
                500000000,  # amount (500 USDC)
                0,  # fee
                0,  # createdAt
                0,  # expiresAt
                0,  # state (LOCKED)
            )
        ]

        service = ReconciliationService(mock_db)
        service.blockchain_service = mock_blockchain_service

        result = await service.reconcile_single_remittance(str(sample_remittance.id))

        assert result.is_matched is True
        assert result.discrepancy_type is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reconcile_single_not_found(self, mock_db):
        """Test remesa no encontrada."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = ReconciliationService(mock_db)

        result = await service.reconcile_single_remittance(str(uuid4()))

        assert result.is_matched is False
        assert result.ledger_status == "NOT_FOUND"
        assert result.discrepancy_type == DiscrepancyType.MISSING_TX

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reconcile_single_missing_onchain(
        self, mock_db, mock_blockchain_service, sample_remittance
    ):
        """Test remesa existe en ledger pero no on-chain."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_remittance
        mock_blockchain_service.call_contract_function.return_value = 0  # No existe on-chain

        service = ReconciliationService(mock_db)
        service.blockchain_service = mock_blockchain_service

        result = await service.reconcile_single_remittance(str(sample_remittance.id))

        # Remesa LOCKED deberia existir on-chain
        assert result.is_matched is False
        assert result.discrepancy_type == DiscrepancyType.MISSING_TX


# ==================== TESTS DE CONSULTAS ====================

class TestReconciliationQueries:
    """Tests de consultas de reconciliacion."""

    @pytest.mark.integration
    def test_get_reconciliation_history(self, mock_db):
        """Test obtener historial de reconciliaciones."""
        logs = [MagicMock(spec=ReconciliationLog) for _ in range(5)]
        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = logs

        service = ReconciliationService(mock_db)
        result = service.get_reconciliation_history(limit=5)

        assert len(result) == 5

    @pytest.mark.integration
    def test_get_unresolved_discrepancies(self, mock_db):
        """Test obtener discrepancias no resueltas."""
        logs = [MagicMock(spec=ReconciliationLog) for _ in range(3)]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = logs

        service = ReconciliationService(mock_db)
        result = service.get_unresolved_discrepancies()

        assert len(result) == 3

    @pytest.mark.integration
    def test_resolve_discrepancy(self, mock_db):
        """Test resolver discrepancia."""
        log = MagicMock(spec=ReconciliationLog)
        log.id = uuid4()
        log.resolved = False
        mock_db.query.return_value.filter.return_value.first.return_value = log

        service = ReconciliationService(mock_db)
        result = service.resolve_discrepancy(
            log_id=str(log.id),
            resolved_by=str(uuid4()),
            action_taken="Discrepancia investigada y corregida manualmente"
        )

        assert result is True
        assert log.resolved is True
        assert log.resolved_at is not None
        mock_db.commit.assert_called()


# ==================== TESTS DE HELPERS ====================

class TestReconciliationHelpers:
    """Tests de funciones auxiliares."""

    @pytest.mark.integration
    def test_wei_to_decimal(self, mock_db):
        """Test conversion wei a decimal."""
        service = ReconciliationService(mock_db)

        # 1000 USDC (6 decimals)
        result = service._wei_to_decimal(1000000000, 6)
        assert result == Decimal("1000")

    @pytest.mark.integration
    def test_decimal_to_wei(self, mock_db):
        """Test conversion decimal a wei."""
        service = ReconciliationService(mock_db)

        result = service._decimal_to_wei(Decimal("1000"), 6)
        assert result == 1000000000

    @pytest.mark.integration
    def test_get_severity_critical(self, mock_db):
        """Test severidad critica (> $1000)."""
        service = ReconciliationService(mock_db)

        severity = service._get_severity(Decimal("5000"))
        assert severity == AlertSeverity.CRITICAL.value

    @pytest.mark.integration
    def test_get_severity_warning(self, mock_db):
        """Test severidad warning ($100-$1000)."""
        service = ReconciliationService(mock_db)

        severity = service._get_severity(Decimal("500"))
        assert severity == AlertSeverity.WARNING.value

    @pytest.mark.integration
    def test_get_severity_info(self, mock_db):
        """Test severidad info (< $100)."""
        service = ReconciliationService(mock_db)

        severity = service._get_severity(Decimal("50"))
        assert severity == AlertSeverity.INFO.value


# ==================== TESTS DE ALERTAS ====================

class TestReconciliationAlerts:
    """Tests del sistema de alertas."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_send_discrepancy_alerts(self, mock_db):
        """Test envio de alertas."""
        log = MagicMock(spec=ReconciliationLog)
        log.id = uuid4()

        discrepancies = [
            {
                "type": DiscrepancyType.LEDGER_ONCHAIN.value,
                "field": "locked",
                "difference": "5000",
                "severity": AlertSeverity.CRITICAL.value,
            },
            {
                "type": DiscrepancyType.STUCK_TX.value,
                "tx_hash": "0x123",
                "severity": AlertSeverity.WARNING.value,
            }
        ]

        service = ReconciliationService(mock_db)

        # Mock notification service
        with patch.object(service, '_send_critical_alert', new_callable=AsyncMock) as mock_critical:
            with patch.object(service, '_send_warning_alert', new_callable=AsyncMock) as mock_warning:
                alerts_sent = await service._send_discrepancy_alerts(discrepancies, log)

                assert alerts_sent == 2
                mock_critical.assert_called_once()
                mock_warning.assert_called_once()


# ==================== TESTS DEL SCHEDULER ====================

class TestSchedulerIntegration:
    """Tests de integracion con el scheduler."""

    @pytest.mark.integration
    def test_scheduler_status(self):
        """Test obtener estado del scheduler."""
        from app.core.scheduler import get_scheduler_status

        status = get_scheduler_status()

        assert "status" in status
        assert "jobs" in status

    @pytest.mark.integration
    def test_create_scheduler(self):
        """Test crear scheduler."""
        from app.core.scheduler import create_scheduler

        scheduler = create_scheduler()

        assert scheduler is not None


# ==================== TESTS DE BALANCE SNAPSHOT ====================

class TestBalanceSnapshot:
    """Tests de BalanceSnapshot."""

    @pytest.mark.integration
    def test_balance_snapshot_creation(self):
        """Test crear snapshot de saldos."""
        snapshot = BalanceSnapshot(
            timestamp=datetime.utcnow(),
            ledger_locked=Decimal("10000.00"),
            ledger_released=Decimal("5000.00"),
            ledger_refunded=Decimal("1000.00"),
            onchain_locked=Decimal("10000.00"),
            onchain_released=Decimal("5000.00"),
            onchain_refunded=Decimal("1000.00"),
            onchain_fees=Decimal("150.00"),
            stablecoin="USDC",
            network="polygon",
        )

        assert snapshot.ledger_locked == Decimal("10000.00")
        assert snapshot.onchain_locked == Decimal("10000.00")
        assert snapshot.stablecoin == "USDC"
