"""
Tests para el Dashboard de Monitoreo y Alertas.

Prueba:
- Schemas de dashboard
- Servicio de alertas
- Servicio de métricas
- Endpoints del dashboard
- WebSocket
"""
import pytest
import json
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

from app.schemas.dashboard import (
    AlertSeverity,
    AlertType,
    AlertStatus,
    ServiceStatus,
    MetricType,
    TimeRange,
    Alert,
    AlertRule,
    AlertSummary,
    RemittanceMetrics,
    FinancialMetrics,
    QueueMetrics,
    SystemMetrics,
    ServiceHealth,
    IntegrationStatus,
    SystemStatus,
    DashboardSnapshot,
    MetricValue,
    MetricSeries,
    CreateAlertRuleRequest,
    WSMessage,
    WSMessageType,
    DEFAULT_THRESHOLDS,
)


# ============ Tests de Schemas ============

class TestDashboardSchemas:
    """Tests para schemas del dashboard."""

    def test_alert_severity_values(self):
        """Test valores de severidad."""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.ERROR.value == "error"
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_alert_type_values(self):
        """Test valores de tipos de alerta."""
        assert AlertType.LOW_BALANCE.value == "low_balance"
        assert AlertType.HIGH_FAILURE_RATE.value == "high_failure_rate"
        assert AlertType.STP_UNREACHABLE.value == "stp.unreachable"

    def test_service_status_values(self):
        """Test valores de estado de servicio."""
        assert ServiceStatus.HEALTHY.value == "healthy"
        assert ServiceStatus.DEGRADED.value == "degraded"
        assert ServiceStatus.DOWN.value == "down"


class TestAlertModel:
    """Tests para modelo de alerta."""

    def test_create_alert(self):
        """Test crear alerta."""
        alert = Alert(
            id="alert_123",
            rule_id="rule_456",
            type=AlertType.LOW_BALANCE,
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            title="Balance bajo",
            message="El balance USDC está por debajo del umbral",
            details={"current_balance": 500, "threshold": 1000},
        )

        assert alert.id == "alert_123"
        assert alert.type == AlertType.LOW_BALANCE
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.ACTIVE

    def test_alert_with_references(self):
        """Test alerta con referencias."""
        alert = Alert(
            id="alert_789",
            rule_id="rule_abc",
            type=AlertType.REMITTANCE_FAILED,
            severity=AlertSeverity.ERROR,
            status=AlertStatus.ACTIVE,
            title="Remesa fallida",
            message="La remesa no pudo completarse",
            remittance_id="rem_xyz",
            job_id="job_123",
        )

        assert alert.remittance_id == "rem_xyz"
        assert alert.job_id == "job_123"


class TestAlertRule:
    """Tests para regla de alerta."""

    def test_create_alert_rule(self):
        """Test crear regla de alerta."""
        rule = AlertRule(
            id="rule_123",
            name="Balance bajo USDC",
            type=AlertType.LOW_BALANCE,
            severity=AlertSeverity.WARNING,
            metric="usdc_balance",
            operator="lt",
            threshold=1000,
            duration_seconds=300,
            notify_channels=["slack", "email"],
        )

        assert rule.name == "Balance bajo USDC"
        assert rule.operator == "lt"
        assert rule.threshold == 1000
        assert "slack" in rule.notify_channels

    def test_create_alert_rule_request_validation(self):
        """Test validación de request de regla."""
        request = CreateAlertRuleRequest(
            name="Test Rule",
            type=AlertType.HIGH_FAILURE_RATE,
            severity=AlertSeverity.ERROR,
            metric="failure_rate",
            operator="gt",
            threshold=0.1,
        )

        assert request.operator == "gt"

    def test_invalid_operator(self):
        """Test operador inválido."""
        with pytest.raises(ValueError):
            CreateAlertRuleRequest(
                name="Test",
                type=AlertType.LOW_BALANCE,
                severity=AlertSeverity.WARNING,
                metric="test",
                operator="invalid",
                threshold=100,
            )


class TestMetrics:
    """Tests para modelos de métricas."""

    def test_remittance_metrics(self):
        """Test métricas de remesas."""
        metrics = RemittanceMetrics(
            total_count=100,
            completed_count=85,
            failed_count=5,
            pending_count=10,
            total_volume_usdc=Decimal("50000"),
            total_volume_mxn=Decimal("875000"),
            success_rate=85.0,
        )

        assert metrics.total_count == 100
        assert metrics.success_rate == 85.0

    def test_financial_metrics(self):
        """Test métricas financieras."""
        metrics = FinancialMetrics(
            usdc_balance=Decimal("10000"),
            mxn_balance=Decimal("175000"),
            current_rate_usdc_mxn=Decimal("17.50"),
        )

        assert metrics.usdc_balance == Decimal("10000")
        assert metrics.current_rate_usdc_mxn == Decimal("17.50")

    def test_queue_metrics(self):
        """Test métricas de cola."""
        metrics = QueueMetrics(
            pending_jobs=15,
            processing_jobs=3,
            completed_jobs=500,
            failed_jobs=10,
            dead_letter_jobs=2,
            active_workers=4,
            error_rate=0.02,
        )

        assert metrics.pending_jobs == 15
        assert metrics.active_workers == 4

    def test_system_metrics(self):
        """Test métricas del sistema."""
        metrics = SystemMetrics(
            cpu_usage=45.5,
            memory_usage=62.3,
            disk_usage=35.0,
            uptime_seconds=86400,
        )

        assert metrics.cpu_usage == 45.5
        assert metrics.uptime_seconds == 86400

    def test_metric_series(self):
        """Test serie temporal de métricas."""
        values = [
            MetricValue(timestamp=datetime.utcnow(), value=10.0),
            MetricValue(timestamp=datetime.utcnow(), value=15.0),
            MetricValue(timestamp=datetime.utcnow(), value=20.0),
        ]

        series = MetricSeries(
            name="requests_per_second",
            type=MetricType.GAUGE,
            values=values,
        )

        assert series.latest == 20.0
        assert series.average == 15.0


class TestServiceHealth:
    """Tests para salud de servicios."""

    def test_service_health_healthy(self):
        """Test servicio saludable."""
        health = ServiceHealth(
            name="database",
            status=ServiceStatus.HEALTHY,
            latency_ms=5.2,
        )

        assert health.status == ServiceStatus.HEALTHY
        assert health.latency_ms == 5.2
        assert health.error_message is None

    def test_service_health_down(self):
        """Test servicio caído."""
        health = ServiceHealth(
            name="redis",
            status=ServiceStatus.DOWN,
            latency_ms=None,
            error_message="Connection refused",
        )

        assert health.status == ServiceStatus.DOWN
        assert health.error_message == "Connection refused"

    def test_system_status(self):
        """Test estado del sistema."""
        integrations = IntegrationStatus(
            database=ServiceHealth(name="database", status=ServiceStatus.HEALTHY),
            redis=ServiceHealth(name="redis", status=ServiceStatus.HEALTHY),
            stp=ServiceHealth(name="stp", status=ServiceStatus.HEALTHY),
            bitso=ServiceHealth(name="bitso", status=ServiceStatus.HEALTHY),
            blockchain=ServiceHealth(name="blockchain", status=ServiceStatus.HEALTHY),
        )

        status = SystemStatus(
            overall_status=ServiceStatus.HEALTHY,
            services=integrations,
            active_alerts=0,
        )

        assert status.is_healthy is True
        assert status.active_alerts == 0


class TestAlertSummary:
    """Tests para resumen de alertas."""

    def test_alert_summary(self):
        """Test resumen de alertas."""
        summary = AlertSummary(
            total_active=5,
            by_severity={"warning": 3, "error": 2},
            by_type={"low_balance": 2, "high_failure_rate": 3},
        )

        assert summary.total_active == 5
        assert summary.by_severity["warning"] == 3


# ============ Tests de Alert Service ============

class TestAlertService:
    """Tests para servicio de alertas."""

    @pytest.fixture
    def mock_db(self):
        """Mock de sesión de base de datos."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_trigger_alert(self, mock_db):
        """Test disparar alerta."""
        from app.services.alert_service import AlertService

        with patch.object(AlertService, '_load_rules'):
            service = AlertService(mock_db)
            service._rules = {}

            with patch.object(service, '_send_notifications', new_callable=AsyncMock):
                alert = await service.trigger_alert(
                    alert_type=AlertType.LOW_BALANCE,
                    severity=AlertSeverity.WARNING,
                    title="Test Alert",
                    message="Test message",
                )

                assert alert.type == AlertType.LOW_BALANCE
                assert alert.severity == AlertSeverity.WARNING
                assert alert.status == AlertStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, mock_db):
        """Test acknowledger alerta."""
        from app.services.alert_service import AlertService

        mock_alert = MagicMock()
        mock_alert.id = "alert_123"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_alert

        with patch.object(AlertService, '_load_rules'):
            service = AlertService(mock_db)

            result = await service.acknowledge_alert(
                alert_id="alert_123",
                acknowledged_by="admin@test.com",
            )

            assert result is True
            assert mock_alert.status == AlertStatus.ACKNOWLEDGED.value

    @pytest.mark.asyncio
    async def test_resolve_alert(self, mock_db):
        """Test resolver alerta."""
        from app.services.alert_service import AlertService

        mock_alert = MagicMock()
        mock_alert.id = "alert_456"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_alert

        with patch.object(AlertService, '_load_rules'):
            service = AlertService(mock_db)
            service._active_alerts["alert_456"] = Alert(
                id="alert_456",
                rule_id="",
                type=AlertType.LOW_BALANCE,
                severity=AlertSeverity.WARNING,
                status=AlertStatus.ACTIVE,
                title="Test",
                message="Test",
            )

            result = await service.resolve_alert("alert_456")

            assert result is True
            assert "alert_456" not in service._active_alerts

    def test_check_condition(self, mock_db):
        """Test verificar condición."""
        from app.services.alert_service import AlertService

        with patch.object(AlertService, '_load_rules'):
            service = AlertService(mock_db)

            assert service._check_condition(5, "gt", 3) is True
            assert service._check_condition(5, "lt", 3) is False
            assert service._check_condition(5, "eq", 5) is True
            assert service._check_condition(5, "gte", 5) is True
            assert service._check_condition(5, "lte", 6) is True

    def test_get_alert_summary(self, mock_db):
        """Test obtener resumen de alertas."""
        from app.services.alert_service import AlertService

        with patch.object(AlertService, '_load_rules'):
            service = AlertService(mock_db)

            # Agregar algunas alertas de prueba
            service._active_alerts = {
                "a1": Alert(
                    id="a1", rule_id="", type=AlertType.LOW_BALANCE,
                    severity=AlertSeverity.WARNING, status=AlertStatus.ACTIVE,
                    title="Test 1", message="Msg 1"
                ),
                "a2": Alert(
                    id="a2", rule_id="", type=AlertType.HIGH_FAILURE_RATE,
                    severity=AlertSeverity.ERROR, status=AlertStatus.ACTIVE,
                    title="Test 2", message="Msg 2"
                ),
            }

            summary = service.get_alert_summary()

            assert summary.total_active == 2
            assert summary.by_severity.get("warning") == 1
            assert summary.by_severity.get("error") == 1


# ============ Tests de Metrics Service ============

class TestMetricsService:
    """Tests para servicio de métricas."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_get_system_metrics(self, mock_db):
        """Test obtener métricas del sistema."""
        from app.services.metrics_service import MetricsService

        service = MetricsService(mock_db)
        metrics = await service.get_system_metrics()

        # Verificar que retorna métricas válidas
        assert metrics.cpu_usage >= 0
        assert metrics.memory_usage >= 0
        assert metrics.uptime_seconds >= 0

    @pytest.mark.asyncio
    async def test_check_database_health(self, mock_db):
        """Test verificar salud de base de datos."""
        from app.services.metrics_service import MetricsService

        mock_db.execute.return_value = True
        service = MetricsService(mock_db)

        health = await service._check_database()

        assert health.name == "database"
        assert health.status == ServiceStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_get_integration_status(self, mock_db):
        """Test obtener estado de integraciones."""
        from app.services.metrics_service import MetricsService

        mock_db.execute.return_value = True
        service = MetricsService(mock_db)
        service._redis = MagicMock()
        service._redis.ping.return_value = True

        with patch.object(service, '_check_stp', new_callable=AsyncMock) as mock_stp:
            with patch.object(service, '_check_bitso', new_callable=AsyncMock) as mock_bitso:
                with patch.object(service, '_check_blockchain', new_callable=AsyncMock) as mock_blockchain:
                    mock_stp.return_value = ServiceHealth(name="stp", status=ServiceStatus.HEALTHY)
                    mock_bitso.return_value = ServiceHealth(name="bitso", status=ServiceStatus.HEALTHY)
                    mock_blockchain.return_value = ServiceHealth(name="blockchain", status=ServiceStatus.HEALTHY)

                    status = await service.get_integration_status()

                    assert status.database.status == ServiceStatus.HEALTHY
                    assert status.stp.status == ServiceStatus.HEALTHY


# ============ Tests de Dashboard Endpoints ============

class TestDashboardEndpoints:
    """Tests para endpoints del dashboard."""

    @pytest.fixture
    def client(self):
        """Cliente de prueba FastAPI."""
        from app.main import app
        return TestClient(app)

    def test_health_check(self, client):
        """Test health check del dashboard."""
        response = client.get("/api/v1/dashboard/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_get_system_status(self, client):
        """Test obtener estado del sistema."""
        with patch('app.api.v1.endpoints.dashboard.get_metrics_service') as mock:
            mock_service = MagicMock()
            mock_service.get_system_status = AsyncMock(return_value=SystemStatus(
                overall_status=ServiceStatus.HEALTHY,
                services=IntegrationStatus(
                    database=ServiceHealth(name="database", status=ServiceStatus.HEALTHY),
                    redis=ServiceHealth(name="redis", status=ServiceStatus.HEALTHY),
                    stp=ServiceHealth(name="stp", status=ServiceStatus.HEALTHY),
                    bitso=ServiceHealth(name="bitso", status=ServiceStatus.HEALTHY),
                    blockchain=ServiceHealth(name="blockchain", status=ServiceStatus.HEALTHY),
                ),
                active_alerts=0,
            ))
            mock.return_value = mock_service

            response = client.get("/api/v1/dashboard/status")
            assert response.status_code == 200
            data = response.json()
            assert data["overall_status"] == "healthy"

    def test_get_alert_summary(self, client):
        """Test obtener resumen de alertas."""
        with patch('app.api.v1.endpoints.dashboard.get_alert_service') as mock:
            mock_service = MagicMock()
            mock_service.get_alert_summary.return_value = AlertSummary(
                total_active=2,
                by_severity={"warning": 1, "error": 1},
                by_type={"low_balance": 1, "high_failure_rate": 1},
                recent_alerts=[],
            )
            mock.return_value = mock_service

            response = client.get("/api/v1/dashboard/alerts/summary")
            assert response.status_code == 200
            data = response.json()
            assert data["total_active"] == 2

    def test_list_alert_rules(self, client):
        """Test listar reglas de alerta."""
        with patch('app.api.v1.endpoints.dashboard.get_alert_service') as mock:
            mock_service = MagicMock()
            mock_service.get_rules.return_value = [
                AlertRule(
                    id="rule_1",
                    name="Test Rule",
                    type=AlertType.LOW_BALANCE,
                    severity=AlertSeverity.WARNING,
                    metric="usdc_balance",
                    operator="lt",
                    threshold=1000,
                )
            ]
            mock.return_value = mock_service

            response = client.get("/api/v1/dashboard/rules")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "Test Rule"


# ============ Tests de WebSocket ============

class TestWebSocket:
    """Tests para WebSocket del dashboard."""

    def test_ws_message_types(self):
        """Test tipos de mensajes WebSocket."""
        assert WSMessageType.METRICS_UPDATE.value == "metrics_update"
        assert WSMessageType.ALERT_TRIGGERED.value == "alert_triggered"
        assert WSMessageType.HEARTBEAT.value == "heartbeat"

    def test_ws_message_model(self):
        """Test modelo de mensaje WebSocket."""
        message = WSMessage(
            type=WSMessageType.METRICS_UPDATE,
            data={"cpu": 45.5, "memory": 62.3},
        )

        assert message.type == WSMessageType.METRICS_UPDATE
        assert message.data["cpu"] == 45.5


# ============ Tests de Constants ============

class TestConstants:
    """Tests para constantes del dashboard."""

    def test_default_thresholds(self):
        """Test umbrales por defecto."""
        assert DEFAULT_THRESHOLDS["low_balance_usdc"] == 1000
        assert DEFAULT_THRESHOLDS["high_failure_rate"] == 0.1
        assert DEFAULT_THRESHOLDS["queue_backlog"] == 100

    def test_time_range_values(self):
        """Test valores de rangos de tiempo."""
        assert TimeRange.LAST_HOUR.value == "1h"
        assert TimeRange.LAST_24_HOURS.value == "24h"
        assert TimeRange.LAST_7_DAYS.value == "7d"
