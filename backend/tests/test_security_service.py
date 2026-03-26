"""
Tests para los Servicios de Seguridad.

Tests unitarios para:
- Multisig Service (Gnosis Safe)
- Security Service (Kill Switch, Alertas, Secrets)
- Detección de intrusiones
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.services.multisig_service import (
    MultisigService,
    MultisigProposal,
    ProposalStatus,
    OperationType,
    MULTISIG_THRESHOLDS,
    MultisigError,
    InsufficientSignaturesError,
    ProposalExpiredError,
)
from app.services.security_service import (
    SecurityService,
    SecurityAlert,
    AlertSeverity,
    AlertType,
    KillSwitchStatus,
    SecretRotationResult,
)
from app.models.blockchain import BlockchainNetwork


# ==================== FIXTURES ====================

@pytest.fixture
def mock_db():
    """Mock de sesión de base de datos."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    return db


@pytest.fixture
def multisig_service(mock_db):
    """Instancia del MultisigService con mocks."""
    with patch('app.services.multisig_service.SessionLocal', return_value=mock_db):
        service = MultisigService(
            network=BlockchainNetwork.POLYGON,
            db=mock_db,
        )
        service.safe_address = "0x" + "1" * 40
        return service


@pytest.fixture
def security_service(mock_db):
    """Instancia del SecurityService con mocks."""
    with patch('app.services.security_service.SessionLocal', return_value=mock_db):
        service = SecurityService(db=mock_db)
        return service


# ==================== TESTS DE MULTISIG ====================

class TestMultisigThresholds:
    """Tests de umbrales de multisig."""

    @pytest.mark.integration
    def test_requires_multisig_above_threshold(self, multisig_service):
        """Test que operaciones sobre umbral requieren multisig."""
        assert multisig_service.requires_multisig("release", Decimal("60000")) is True
        assert multisig_service.requires_multisig("release", Decimal("50001")) is True

    @pytest.mark.integration
    def test_not_requires_multisig_below_threshold(self, multisig_service):
        """Test que operaciones bajo umbral no requieren multisig."""
        assert multisig_service.requires_multisig("release", Decimal("40000")) is False
        assert multisig_service.requires_multisig("release", Decimal("1000")) is False

    @pytest.mark.integration
    def test_config_change_always_requires_multisig(self, multisig_service):
        """Test que cambios de configuración siempre requieren multisig."""
        assert multisig_service.requires_multisig("config_change", Decimal("0")) is True
        assert multisig_service.requires_multisig("pause", Decimal("0")) is True
        assert multisig_service.requires_multisig("unpause", Decimal("0")) is True

    @pytest.mark.integration
    def test_get_threshold(self, multisig_service):
        """Test obtener umbral por operación."""
        assert multisig_service.get_threshold("release") == Decimal("50000")
        assert multisig_service.get_threshold("refund") == Decimal("25000")
        assert multisig_service.get_threshold("unknown") == Decimal("50000")  # default


class TestMultisigProposals:
    """Tests de propuestas multisig."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_proposal(self, multisig_service, mock_db):
        """Test crear propuesta."""
        with patch.object(multisig_service, 'get_safe_info', new_callable=AsyncMock) as mock_info:
            mock_info.return_value = MagicMock(
                address="0x" + "1" * 40,
                owners=["0x" + "a" * 40, "0x" + "b" * 40],
                threshold=2,
                nonce=10,
            )

            with patch.object(multisig_service, '_register_safe_transaction', new_callable=AsyncMock):
                proposal = await multisig_service.create_proposal(
                    operation_type="release",
                    target_contract="0x" + "2" * 40,
                    calldata="0x12345678",
                    amount_usd=Decimal("75000"),
                    description="Release escrow #123",
                )

                assert proposal is not None
                assert proposal.status == ProposalStatus.PENDING
                assert proposal.required_signatures == 2
                mock_db.add.assert_called()
                mock_db.commit.assert_called()

    @pytest.mark.integration
    def test_proposal_is_ready_to_execute(self):
        """Test verificar si propuesta está lista."""
        proposal = MultisigProposal(
            id=str(uuid4()),
            safe_address="0x123",
            operation_type=OperationType.RELEASE,
            description="Test",
            target_contract="0x456",
            calldata="0x",
            value=0,
            amount_usd=Decimal("1000"),
            status=ProposalStatus.PENDING,
            required_signatures=2,
            current_signatures=2,
            signers=["0xa", "0xb"],
            signatures=[],
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )

        assert proposal.is_ready_to_execute() is True

        proposal.current_signatures = 1
        assert proposal.is_ready_to_execute() is False

    @pytest.mark.integration
    def test_proposal_is_expired(self):
        """Test verificar si propuesta expiró."""
        proposal = MultisigProposal(
            id=str(uuid4()),
            safe_address="0x123",
            operation_type=OperationType.RELEASE,
            description="Test",
            target_contract="0x456",
            calldata="0x",
            value=0,
            amount_usd=Decimal("1000"),
            status=ProposalStatus.PENDING,
            required_signatures=2,
            current_signatures=0,
            signers=[],
            signatures=[],
            created_at=datetime.utcnow() - timedelta(hours=48),
            expires_at=datetime.utcnow() - timedelta(hours=24),
        )

        assert proposal.is_expired() is True


# ==================== TESTS DE KILL SWITCH ====================

class TestKillSwitch:
    """Tests del Kill Switch."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_activate_kill_switch(self, security_service, mock_db):
        """Test activar kill switch."""
        with patch.object(security_service, 'create_alert', new_callable=AsyncMock):
            with patch.object(security_service, '_pause_smart_contracts', new_callable=AsyncMock):
                status = await security_service.activate_kill_switch(
                    reason="Test emergency",
                    initiated_by="admin@test.com",
                )

                assert status.is_active is True
                assert status.reason == "Test emergency"
                assert security_service.is_system_paused() is True
                mock_db.add.assert_called()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_deactivate_kill_switch(self, security_service, mock_db):
        """Test desactivar kill switch."""
        # Primero activar
        security_service._kill_switch_active = True
        security_service._kill_switch_info = KillSwitchStatus(
            is_active=True,
            activated_at=datetime.utcnow(),
            activated_by="admin",
            reason="test",
            affected_services=["service1"],
            estimated_resolution=None,
        )

        with patch.object(security_service, 'create_alert', new_callable=AsyncMock):
            with patch.object(security_service, '_unpause_smart_contracts', new_callable=AsyncMock):
                status = await security_service.deactivate_kill_switch(
                    initiated_by="admin@test.com",
                    resolution_notes="Issue resolved",
                )

                assert status.is_active is False
                assert security_service.is_system_paused() is False

    @pytest.mark.integration
    def test_is_system_paused(self, security_service):
        """Test verificar si sistema está pausado."""
        assert security_service.is_system_paused() is False

        security_service._kill_switch_active = True
        assert security_service.is_system_paused() is True

    @pytest.mark.integration
    def test_get_kill_switch_status(self, security_service):
        """Test obtener estado del kill switch."""
        status = security_service.get_kill_switch_status()
        assert status.is_active is False


# ==================== TESTS DE ALERTAS ====================

class TestSecurityAlerts:
    """Tests de alertas de seguridad."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_alert(self, security_service, mock_db):
        """Test crear alerta."""
        with patch.object(security_service, '_send_alert_notifications', new_callable=AsyncMock):
            alert = await security_service.create_alert(
                severity=AlertSeverity.HIGH,
                alert_type=AlertType.UNUSUAL_ACTIVITY,
                title="Suspicious Activity",
                description="Unusual transaction pattern detected",
                source_ip="192.168.1.1",
            )

            assert alert is not None
            assert alert.severity == AlertSeverity.HIGH
            assert alert.alert_type == AlertType.UNUSUAL_ACTIVITY
            mock_db.add.assert_called()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_alert_callback(self, security_service, mock_db):
        """Test callback de alertas."""
        callback = MagicMock()
        security_service.register_alert_callback(callback)

        with patch.object(security_service, '_send_alert_notifications', new_callable=AsyncMock):
            await security_service.create_alert(
                severity=AlertSeverity.MEDIUM,
                alert_type=AlertType.FAILED_AUTH,
                title="Test",
                description="Test alert",
            )

        callback.assert_called_once()

    @pytest.mark.integration
    def test_acknowledge_alert(self, security_service, mock_db):
        """Test reconocer alerta."""
        mock_alert = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_alert

        result = security_service.acknowledge_alert(
            alert_id=str(uuid4()),
            acknowledged_by="admin@test.com",
        )

        assert result is True
        assert mock_alert.acknowledged is True


# ==================== TESTS DE DETECCIÓN DE INTRUSIONES ====================

class TestIntrusionDetection:
    """Tests de detección de intrusiones."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_record_failed_auth(self, security_service, mock_db):
        """Test registrar autenticación fallida."""
        with patch.object(security_service, '_handle_brute_force', new_callable=AsyncMock):
            await security_service.record_failed_auth(
                source_ip="192.168.1.100",
                user_identifier="test@example.com",
            )

            assert "192.168.1.100" in security_service._failed_auth_tracker
            assert len(security_service._failed_auth_tracker["192.168.1.100"]) == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_brute_force_detection(self, security_service, mock_db):
        """Test detección de fuerza bruta."""
        with patch.object(security_service, 'block_ip', new_callable=AsyncMock) as mock_block:
            with patch.object(security_service, 'create_alert', new_callable=AsyncMock):
                # Simular múltiples intentos fallidos
                for i in range(6):
                    await security_service.record_failed_auth(
                        source_ip="192.168.1.200",
                    )

                # Debería haber bloqueado la IP
                mock_block.assert_called()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_block_ip(self, security_service, mock_db):
        """Test bloquear IP."""
        with patch.object(security_service, 'create_alert', new_callable=AsyncMock):
            await security_service.block_ip(
                ip_address="10.0.0.1",
                reason="Malicious activity",
                hours=24,
            )

            assert "10.0.0.1" in security_service._blocked_ips
            mock_db.add.assert_called()

    @pytest.mark.integration
    def test_is_ip_blocked(self, security_service):
        """Test verificar si IP está bloqueada."""
        security_service._blocked_ips.add("1.2.3.4")

        assert security_service.is_ip_blocked("1.2.3.4") is True
        assert security_service.is_ip_blocked("5.6.7.8") is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rate_limit(self, security_service, mock_db):
        """Test rate limiting."""
        with patch.object(security_service, 'create_alert', new_callable=AsyncMock):
            # Primeras requests OK
            for i in range(50):
                result = await security_service.check_rate_limit("user123")
                assert result is True

            # Siguiente debería fallar (default 100/min, pero test es más rápido)
            # Reset para test
            security_service._rate_limit_tracker["user_test"] = [
                datetime.utcnow() for _ in range(100)
            ]
            result = await security_service.check_rate_limit("user_test")
            assert result is False


# ==================== TESTS DE ROTACIÓN DE SECRETOS ====================

class TestSecretRotation:
    """Tests de rotación de secretos."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rotate_secret_no_vault(self, security_service, mock_db):
        """Test rotación sin Vault configurado."""
        result = await security_service.rotate_secret(
            secret_name="test_api_key",
            secret_type="api_key",
        )

        assert result.success is False
        assert "Vault no configurado" in result.error

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rotate_secret_with_vault(self, security_service, mock_db):
        """Test rotación con Vault."""
        with patch('app.services.security_service.VAULT_TOKEN', 'test-token'):
            with patch.object(security_service, '_get_vault_secret_version', new_callable=AsyncMock) as mock_version:
                mock_version.return_value = 1

                with patch.object(security_service, '_update_vault_secret', new_callable=AsyncMock) as mock_update:
                    mock_update.return_value = True

                    result = await security_service.rotate_secret(
                        secret_name="test_api_key",
                        secret_type="api_key",
                    )

                    assert result.success is True
                    assert result.version == 2
                    mock_db.add.assert_called()

    @pytest.mark.integration
    def test_generate_secret_value(self, security_service):
        """Test generación de valores de secretos."""
        api_key = security_service._generate_secret_value("api_key")
        assert api_key.startswith("fk_")
        assert len(api_key) > 20

        db_pass = security_service._generate_secret_value("db_password")
        assert len(db_pass) >= 24

        jwt = security_service._generate_secret_value("jwt_secret")
        assert len(jwt) == 64  # hex


# ==================== TESTS DE MÉTRICAS ====================

class TestSecurityMetrics:
    """Tests de métricas de seguridad."""

    @pytest.mark.integration
    def test_metrics_defined(self):
        """Test que las métricas están definidas."""
        from app.services.security_service import (
            KILL_SWITCH_ACTIVATIONS,
            SECURITY_ALERTS,
            FAILED_AUTH_ATTEMPTS,
            SECRET_ROTATIONS,
            SYSTEM_STATUS,
            INTRUSION_SCORE,
        )

        assert KILL_SWITCH_ACTIVATIONS is not None
        assert SECURITY_ALERTS is not None
        assert FAILED_AUTH_ATTEMPTS is not None
        assert SECRET_ROTATIONS is not None
        assert SYSTEM_STATUS is not None
        assert INTRUSION_SCORE is not None

    @pytest.mark.integration
    def test_multisig_metrics_defined(self):
        """Test métricas de multisig."""
        from app.services.multisig_service import (
            PROPOSALS_CREATED,
            PROPOSALS_EXECUTED,
            PROPOSALS_PENDING,
            SIGNATURE_TIME,
        )

        assert PROPOSALS_CREATED is not None
        assert PROPOSALS_EXECUTED is not None
        assert PROPOSALS_PENDING is not None
        assert SIGNATURE_TIME is not None


# ==================== TESTS DE SEVERIDAD ====================

class TestAlertSeverity:
    """Tests de niveles de severidad."""

    @pytest.mark.integration
    def test_severity_values(self):
        """Test valores de severidad."""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.LOW.value == "low"
        assert AlertSeverity.MEDIUM.value == "medium"
        assert AlertSeverity.HIGH.value == "high"
        assert AlertSeverity.CRITICAL.value == "critical"

    @pytest.mark.integration
    def test_alert_types(self):
        """Test tipos de alerta."""
        assert AlertType.BRUTE_FORCE.value == "brute_force"
        assert AlertType.KILL_SWITCH.value == "kill_switch"
        assert AlertType.INTRUSION_DETECTED.value == "intrusion_detected"
