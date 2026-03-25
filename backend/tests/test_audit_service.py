"""
Tests unitarios para servicios de Auditoria.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from decimal import Decimal
from datetime import datetime, timedelta

from app.services.audit import (
    SlitherAuditService,
    TransactionMonitoringService,
    IncidentResponseService,
    AlertSeverity,
    AlertType,
    IncidentSeverity,
    IncidentStatus,
    Alert,
    Incident,
    MonitoringRule,
)


# ==================== SlitherAuditService Tests ====================


class TestSlitherAuditServiceInit:
    """Tests de inicializacion de SlitherAuditService."""

    @pytest.mark.unit
    @pytest.mark.audit
    def test_init_creates_empty_cache(self):
        """Test que la inicializacion crea cache vacio."""
        service = SlitherAuditService()
        assert service._audit_cache == {}

    @pytest.mark.unit
    @pytest.mark.audit
    def test_init_sets_slither_path(self):
        """Test que establece path de slither."""
        service = SlitherAuditService()
        assert service._slither_path == "slither"


class TestSlitherAuditServiceDetectors:
    """Tests de detectores de Slither."""

    @pytest.mark.unit
    @pytest.mark.audit
    def test_list_detectors_returns_categories(self):
        """Test que list_detectors retorna categorias."""
        service = SlitherAuditService()
        detectors = service.list_detectors()

        assert len(detectors) == 3
        categories = [d["category"] for d in detectors]
        assert "high" in categories
        assert "medium" in categories
        assert "low" in categories

    @pytest.mark.unit
    @pytest.mark.audit
    def test_high_detectors_exist(self):
        """Test que existen detectores de alta severidad."""
        service = SlitherAuditService()
        assert len(service.HIGH_DETECTORS) > 0
        assert "reentrancy-eth" in service.HIGH_DETECTORS

    @pytest.mark.unit
    @pytest.mark.audit
    def test_medium_detectors_exist(self):
        """Test que existen detectores de severidad media."""
        service = SlitherAuditService()
        assert len(service.MEDIUM_DETECTORS) > 0
        assert "tx-origin" in service.MEDIUM_DETECTORS


class TestSlitherAuditServiceInstallCheck:
    """Tests de verificacion de instalacion de Slither."""

    @pytest.mark.unit
    @pytest.mark.audit
    def test_is_slither_installed_true(self):
        """Test cuando Slither esta instalado."""
        service = SlitherAuditService()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = service.is_slither_installed()
            assert result is True

    @pytest.mark.unit
    @pytest.mark.audit
    def test_is_slither_installed_false_not_found(self):
        """Test cuando Slither no esta instalado."""
        service = SlitherAuditService()

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = service.is_slither_installed()
            assert result is False

    @pytest.mark.unit
    @pytest.mark.audit
    def test_is_slither_installed_false_timeout(self):
        """Test cuando Slither timeout."""
        service = SlitherAuditService()

        with patch('subprocess.run') as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired("slither", 10)
            result = service.is_slither_installed()
            assert result is False


class TestSlitherAuditServiceSecurityScore:
    """Tests de calculo de security score."""

    @pytest.mark.unit
    @pytest.mark.audit
    def test_security_score_perfect(self):
        """Test score perfecto sin vulnerabilidades."""
        service = SlitherAuditService()
        vulnerabilities = {
            "high": 0,
            "medium": 0,
            "low": 0,
            "informational": 0,
        }
        score = service._calculate_security_score(vulnerabilities)
        assert score == 100

    @pytest.mark.unit
    @pytest.mark.audit
    def test_security_score_high_penalty(self):
        """Test penalizacion por vulnerabilidades altas."""
        service = SlitherAuditService()
        vulnerabilities = {
            "high": 2,
            "medium": 0,
            "low": 0,
            "informational": 0,
        }
        score = service._calculate_security_score(vulnerabilities)
        assert score == 60  # 100 - (2 * 20)

    @pytest.mark.unit
    @pytest.mark.audit
    def test_security_score_minimum_zero(self):
        """Test que el score minimo es 0."""
        service = SlitherAuditService()
        vulnerabilities = {
            "high": 10,
            "medium": 10,
            "low": 10,
            "informational": 10,
        }
        score = service._calculate_security_score(vulnerabilities)
        assert score == 0

    @pytest.mark.unit
    @pytest.mark.audit
    def test_security_score_mixed_vulnerabilities(self):
        """Test score con mezcla de vulnerabilidades."""
        service = SlitherAuditService()
        vulnerabilities = {
            "high": 1,
            "medium": 2,
            "low": 3,
            "informational": 5,
        }
        # 100 - 20 - 20 - 15 - 5 = 40
        score = service._calculate_security_score(vulnerabilities)
        assert score == 40


class TestSlitherAuditServiceRecommendations:
    """Tests de generacion de recomendaciones."""

    @pytest.mark.unit
    @pytest.mark.audit
    def test_recommendations_for_high_severity(self):
        """Test recomendaciones para vulnerabilidades altas."""
        service = SlitherAuditService()
        vulnerabilities = {"high": 1, "medium": 0, "low": 0, "informational": 0}
        recommendations = service._generate_recommendations(vulnerabilities)

        assert any("CRITICO" in r for r in recommendations)
        assert any("auditoria externa" in r.lower() for r in recommendations)

    @pytest.mark.unit
    @pytest.mark.audit
    def test_recommendations_always_include_general(self):
        """Test que siempre incluye recomendaciones generales."""
        service = SlitherAuditService()
        vulnerabilities = {"high": 0, "medium": 0, "low": 0, "informational": 0}
        recommendations = service._generate_recommendations(vulnerabilities)

        assert any("tests unitarios" in r.lower() for r in recommendations)
        assert any("OpenZeppelin" in r for r in recommendations)


class TestSlitherAuditServiceParseOutput:
    """Tests de parseo de salida de Slither."""

    @pytest.mark.unit
    @pytest.mark.audit
    def test_parse_empty_output(self):
        """Test parseo de salida vacia."""
        service = SlitherAuditService()
        output = {"results": {"detectors": []}}
        result = service._parse_slither_output(output)

        assert result["high"] == 0
        assert result["medium"] == 0
        assert result["low"] == 0
        assert result["informational"] == 0

    @pytest.mark.unit
    @pytest.mark.audit
    def test_parse_with_high_vulnerability(self):
        """Test parseo con vulnerabilidad alta."""
        service = SlitherAuditService()
        output = {
            "results": {
                "detectors": [
                    {
                        "check": "reentrancy-eth",
                        "impact": "High",
                        "description": "Reentrancy vulnerability",
                        "elements": [{"source_mapping": {"filename_short": "Contract.sol"}}],
                    }
                ]
            }
        }
        result = service._parse_slither_output(output)

        assert result["high"] == 1
        assert len(result["high_issues"]) == 1
        assert result["high_issues"][0]["type"] == "reentrancy-eth"


# ==================== TransactionMonitoringService Tests ====================


class TestTransactionMonitoringServiceInit:
    """Tests de inicializacion de TransactionMonitoringService."""

    @pytest.mark.unit
    @pytest.mark.audit
    def test_init_creates_empty_alerts(self):
        """Test que inicializa lista vacia de alertas."""
        service = TransactionMonitoringService()
        assert service.alerts == []

    @pytest.mark.unit
    @pytest.mark.audit
    def test_init_creates_default_rules(self):
        """Test que crea reglas por defecto."""
        service = TransactionMonitoringService()
        assert len(service.rules) > 0

        rule_types = [r.alert_type for r in service.rules]
        assert AlertType.HIGH_VALUE_TRANSFER in rule_types
        assert AlertType.UNUSUAL_GAS in rule_types


class TestTransactionMonitoringServiceAnalyze:
    """Tests de analisis de transacciones."""

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_analyze_high_value_transaction(self, sample_transaction_data):
        """Test deteccion de transaccion de alto valor."""
        service = TransactionMonitoringService()

        alerts = await service.analyze_transaction(
            tx_hash=sample_transaction_data["tx_hash"],
            from_address=sample_transaction_data["from_address"],
            to_address=sample_transaction_data["to_address"],
            value=Decimal("50000"),  # Alto valor
            gas_price=sample_transaction_data["gas_price"],
        )

        assert len(alerts) > 0
        high_value_alerts = [a for a in alerts if a.type == AlertType.HIGH_VALUE_TRANSFER]
        assert len(high_value_alerts) > 0

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_analyze_normal_transaction(self, sample_transaction_data):
        """Test que transaccion normal no genera alertas de valor."""
        service = TransactionMonitoringService()

        alerts = await service.analyze_transaction(
            tx_hash=sample_transaction_data["tx_hash"],
            from_address=sample_transaction_data["from_address"],
            to_address=sample_transaction_data["to_address"],
            value=Decimal("100"),  # Valor normal
            gas_price=30_000_000_000,  # Gas normal
        )

        high_value_alerts = [a for a in alerts if a.type == AlertType.HIGH_VALUE_TRANSFER]
        assert len(high_value_alerts) == 0

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_analyze_unusual_gas(self, sample_transaction_data):
        """Test deteccion de gas inusual."""
        service = TransactionMonitoringService()

        alerts = await service.analyze_transaction(
            tx_hash=sample_transaction_data["tx_hash"],
            from_address=sample_transaction_data["from_address"],
            to_address=sample_transaction_data["to_address"],
            value=Decimal("100"),
            gas_price=300_000_000_000,  # 300 Gwei - 10x promedio
        )

        gas_alerts = [a for a in alerts if a.type == AlertType.UNUSUAL_GAS]
        assert len(gas_alerts) > 0

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_analyze_blacklisted_address(self):
        """Test deteccion de direccion en blacklist."""
        service = TransactionMonitoringService()

        alerts = await service.analyze_transaction(
            tx_hash="0x" + "a" * 64,
            from_address="0x0000000000000000000000000000000000000000",
            to_address="0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16",
            value=Decimal("100"),
            gas_price=30_000_000_000,
        )

        blacklist_alerts = [a for a in alerts if a.type == AlertType.BLACKLISTED_ADDRESS]
        assert len(blacklist_alerts) > 0
        assert blacklist_alerts[0].severity == AlertSeverity.CRITICAL

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_analyze_reentrancy_pattern(self):
        """Test deteccion de patron de reentrancia."""
        service = TransactionMonitoringService()

        alerts = await service.analyze_transaction(
            tx_hash="0x" + "a" * 64,
            from_address="0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16",
            to_address="0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
            value=Decimal("100"),
            gas_price=30_000_000_000,
            input_data="0x3ccfd60b",  # withdraw()
        )

        reentrancy_alerts = [a for a in alerts if a.type == AlertType.REENTRANCY_PATTERN]
        assert len(reentrancy_alerts) > 0


class TestTransactionMonitoringServiceAlerts:
    """Tests de gestion de alertas."""

    @pytest.mark.unit
    @pytest.mark.audit
    def test_get_recent_alerts_empty(self):
        """Test obtener alertas cuando no hay ninguna."""
        service = TransactionMonitoringService()
        alerts = service.get_recent_alerts()
        assert alerts == []

    @pytest.mark.unit
    @pytest.mark.audit
    def test_get_recent_alerts_with_limit(self):
        """Test limite de alertas."""
        service = TransactionMonitoringService()

        # Agregar alertas manualmente
        for i in range(10):
            service.alerts.append(Alert(
                id=f"alert-{i}",
                type=AlertType.HIGH_VALUE_TRANSFER,
                severity=AlertSeverity.HIGH,
                title=f"Alert {i}",
                description="Test alert",
            ))

        alerts = service.get_recent_alerts(limit=5)
        assert len(alerts) == 5

    @pytest.mark.unit
    @pytest.mark.audit
    def test_get_recent_alerts_filter_by_severity(self):
        """Test filtro por severidad."""
        service = TransactionMonitoringService()

        service.alerts.append(Alert(
            id="alert-high",
            type=AlertType.HIGH_VALUE_TRANSFER,
            severity=AlertSeverity.HIGH,
            title="High Alert",
            description="Test",
        ))
        service.alerts.append(Alert(
            id="alert-low",
            type=AlertType.UNUSUAL_GAS,
            severity=AlertSeverity.LOW,
            title="Low Alert",
            description="Test",
        ))

        alerts = service.get_recent_alerts(severity=AlertSeverity.HIGH)
        assert len(alerts) == 1
        assert alerts[0].id == "alert-high"

    @pytest.mark.unit
    @pytest.mark.audit
    def test_acknowledge_alert_success(self):
        """Test reconocimiento de alerta exitoso."""
        service = TransactionMonitoringService()
        service.alerts.append(Alert(
            id="alert-1",
            type=AlertType.HIGH_VALUE_TRANSFER,
            severity=AlertSeverity.HIGH,
            title="Test Alert",
            description="Test",
        ))

        result = service.acknowledge_alert("alert-1", "admin@fincore.mx")

        assert result is True
        assert service.alerts[0].acknowledged is True
        assert service.alerts[0].acknowledged_by == "admin@fincore.mx"

    @pytest.mark.unit
    @pytest.mark.audit
    def test_acknowledge_alert_not_found(self):
        """Test reconocimiento de alerta no encontrada."""
        service = TransactionMonitoringService()
        result = service.acknowledge_alert("nonexistent")
        assert result is False


class TestTransactionMonitoringServiceStatistics:
    """Tests de estadisticas de monitoreo."""

    @pytest.mark.unit
    @pytest.mark.audit
    def test_get_statistics_empty(self):
        """Test estadisticas vacias."""
        service = TransactionMonitoringService()
        stats = service.get_alert_statistics()

        assert stats["total_alerts"] == 0
        assert stats["acknowledged"] == 0
        assert stats["unacknowledged"] == 0

    @pytest.mark.unit
    @pytest.mark.audit
    def test_get_statistics_with_alerts(self):
        """Test estadisticas con alertas."""
        service = TransactionMonitoringService()

        service.alerts.append(Alert(
            id="alert-1",
            type=AlertType.HIGH_VALUE_TRANSFER,
            severity=AlertSeverity.HIGH,
            title="Alert 1",
            description="Test",
            acknowledged=True,
        ))
        service.alerts.append(Alert(
            id="alert-2",
            type=AlertType.UNUSUAL_GAS,
            severity=AlertSeverity.MEDIUM,
            title="Alert 2",
            description="Test",
        ))

        stats = service.get_alert_statistics()

        assert stats["total_alerts"] == 2
        assert stats["acknowledged"] == 1
        assert stats["unacknowledged"] == 1
        assert stats["by_severity"]["high"] == 1
        assert stats["by_severity"]["medium"] == 1


class TestTransactionMonitoringServiceRules:
    """Tests de gestion de reglas."""

    @pytest.mark.unit
    @pytest.mark.audit
    def test_add_rule(self):
        """Test agregar regla."""
        service = TransactionMonitoringService()
        initial_count = len(service.rules)

        new_rule = MonitoringRule(
            id="custom_rule",
            name="Custom Rule",
            description="Test rule",
            alert_type=AlertType.CONTRACT_INTERACTION,
            severity=AlertSeverity.MEDIUM,
            threshold=Decimal("1000"),
        )
        service.add_rule(new_rule)

        assert len(service.rules) == initial_count + 1

    @pytest.mark.unit
    @pytest.mark.audit
    def test_remove_rule(self):
        """Test eliminar regla."""
        service = TransactionMonitoringService()
        rule_id = service.rules[0].id
        initial_count = len(service.rules)

        result = service.remove_rule(rule_id)

        assert result is True
        assert len(service.rules) == initial_count - 1

    @pytest.mark.unit
    @pytest.mark.audit
    def test_remove_rule_not_found(self):
        """Test eliminar regla no encontrada."""
        service = TransactionMonitoringService()
        result = service.remove_rule("nonexistent")
        assert result is False


# ==================== IncidentResponseService Tests ====================


class TestIncidentResponseServiceInit:
    """Tests de inicializacion de IncidentResponseService."""

    @pytest.mark.unit
    @pytest.mark.audit
    def test_init_creates_empty_incidents(self):
        """Test que inicializa sin incidentes."""
        monitoring = TransactionMonitoringService()
        service = IncidentResponseService(monitoring)

        assert service.incidents == {}
        assert service._circuit_breaker_active is False


class TestIncidentResponseServiceCreate:
    """Tests de creacion de incidentes."""

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_create_incident_basic(self):
        """Test creacion de incidente basico."""
        monitoring = TransactionMonitoringService()
        service = IncidentResponseService(monitoring)

        incident = await service.create_incident(
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.SEV3,
            detected_by="admin@fincore.mx",
        )

        assert incident.id is not None
        assert incident.title == "Test Incident"
        assert incident.status == IncidentStatus.DETECTED
        assert len(incident.actions_taken) > 0

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_create_sev1_activates_circuit_breaker(self):
        """Test que SEV1 activa circuit breaker."""
        monitoring = TransactionMonitoringService()
        service = IncidentResponseService(monitoring)

        incident = await service.create_incident(
            title="Critical Incident",
            description="Critical issue",
            severity=IncidentSeverity.SEV1,
            detected_by="admin@fincore.mx",
        )

        assert service._circuit_breaker_active is True
        # Verificar que se registro la accion
        cb_actions = [a for a in incident.actions_taken if a["action"] == "circuit_breaker_activated"]
        assert len(cb_actions) > 0

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_create_incident_with_contracts(self):
        """Test creacion con contratos afectados."""
        monitoring = TransactionMonitoringService()
        service = IncidentResponseService(monitoring)

        contracts = ["0x123...", "0x456..."]
        incident = await service.create_incident(
            title="Contract Incident",
            description="Issue with contracts",
            severity=IncidentSeverity.SEV2,
            detected_by="admin@fincore.mx",
            affected_contracts=contracts,
        )

        assert incident.affected_contracts == contracts


class TestIncidentResponseServiceLifecycle:
    """Tests del ciclo de vida de incidentes."""

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_contain_incident(self):
        """Test contencion de incidente."""
        monitoring = TransactionMonitoringService()
        service = IncidentResponseService(monitoring)

        incident = await service.create_incident(
            title="Test Incident",
            description="Test",
            severity=IncidentSeverity.SEV2,
            detected_by="admin@fincore.mx",
        )

        result = await service.contain_incident(incident.id, "ops@fincore.mx")

        assert result is True
        assert incident.status == IncidentStatus.CONTAINED
        assert incident.contained_at is not None

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_contain_incident_not_found(self):
        """Test contencion de incidente no encontrado."""
        monitoring = TransactionMonitoringService()
        service = IncidentResponseService(monitoring)

        result = await service.contain_incident("nonexistent", "admin@fincore.mx")
        assert result is False

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_resolve_incident(self):
        """Test resolucion de incidente."""
        monitoring = TransactionMonitoringService()
        service = IncidentResponseService(monitoring)

        incident = await service.create_incident(
            title="Test Incident",
            description="Test",
            severity=IncidentSeverity.SEV2,
            detected_by="admin@fincore.mx",
        )

        await service.contain_incident(incident.id, "ops@fincore.mx")
        result = await service.resolve_incident(
            incident.id,
            "ops@fincore.mx",
            root_cause="Configuration error"
        )

        assert result is True
        assert incident.status == IncidentStatus.RESOLVED
        assert incident.resolved_at is not None
        assert incident.root_cause == "Configuration error"

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_resolve_sev1_deactivates_circuit_breaker(self):
        """Test que resolver SEV1 desactiva circuit breaker."""
        monitoring = TransactionMonitoringService()
        service = IncidentResponseService(monitoring)

        incident = await service.create_incident(
            title="Critical",
            description="Critical",
            severity=IncidentSeverity.SEV1,
            detected_by="admin@fincore.mx",
        )

        assert service._circuit_breaker_active is True

        await service.resolve_incident(incident.id, "ops@fincore.mx")

        assert service._circuit_breaker_active is False


class TestIncidentResponseServiceQueries:
    """Tests de consultas de incidentes."""

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_get_active_incidents(self):
        """Test obtener incidentes activos."""
        monitoring = TransactionMonitoringService()
        service = IncidentResponseService(monitoring)

        # Crear incidentes
        inc1 = await service.create_incident(
            title="Active 1",
            description="Test",
            severity=IncidentSeverity.SEV3,
            detected_by="admin@fincore.mx",
        )
        inc2 = await service.create_incident(
            title="Active 2",
            description="Test",
            severity=IncidentSeverity.SEV4,
            detected_by="admin@fincore.mx",
        )

        # Resolver uno
        await service.resolve_incident(inc2.id, "admin@fincore.mx")

        active = service.get_active_incidents()
        assert len(active) == 1
        assert active[0].id == inc1.id

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_get_incident_statistics(self):
        """Test estadisticas de incidentes."""
        monitoring = TransactionMonitoringService()
        service = IncidentResponseService(monitoring)

        await service.create_incident(
            title="SEV2 Incident",
            description="Test",
            severity=IncidentSeverity.SEV2,
            detected_by="admin@fincore.mx",
        )

        stats = service.get_incident_statistics()

        assert stats["total_incidents"] == 1
        assert stats["active_incidents"] == 1
        assert stats["by_severity"]["sev2"] == 1


class TestIncidentResponseServicePostmortem:
    """Tests de reportes post-mortem."""

    @pytest.mark.unit
    @pytest.mark.audit
    @pytest.mark.asyncio
    async def test_generate_postmortem_resolved_incident(self):
        """Test generar post-mortem de incidente resuelto."""
        monitoring = TransactionMonitoringService()
        service = IncidentResponseService(monitoring)

        incident = await service.create_incident(
            title="Test Incident",
            description="Test description",
            severity=IncidentSeverity.SEV2,
            detected_by="admin@fincore.mx",
        )

        await service.contain_incident(incident.id, "ops@fincore.mx")
        await service.resolve_incident(
            incident.id,
            "ops@fincore.mx",
            root_cause="Human error"
        )

        report = service.generate_postmortem_report(incident.id)

        assert report["incident_id"] == incident.id
        assert report["root_cause"] == "Human error"
        assert report["timeline"]["resolved_at"] is not None
        assert "recommendations" in report

    @pytest.mark.unit
    @pytest.mark.audit
    def test_generate_postmortem_not_found(self):
        """Test post-mortem de incidente no encontrado."""
        monitoring = TransactionMonitoringService()
        service = IncidentResponseService(monitoring)

        report = service.generate_postmortem_report("nonexistent")
        assert "error" in report


# ==================== Alert Dataclass Tests ====================


class TestAlertDataclass:
    """Tests de la dataclass Alert."""

    @pytest.mark.unit
    def test_alert_creation_defaults(self):
        """Test creacion de alerta con valores por defecto."""
        alert = Alert(
            id="alert-1",
            type=AlertType.HIGH_VALUE_TRANSFER,
            severity=AlertSeverity.HIGH,
            title="Test Alert",
            description="Test description",
        )

        assert alert.acknowledged is False
        assert alert.acknowledged_by is None
        assert alert.transaction_hash is None

    @pytest.mark.unit
    def test_alert_with_transaction(self):
        """Test alerta con hash de transaccion."""
        alert = Alert(
            id="alert-1",
            type=AlertType.HIGH_VALUE_TRANSFER,
            severity=AlertSeverity.HIGH,
            title="Test Alert",
            description="Test description",
            transaction_hash="0x" + "a" * 64,
        )

        assert alert.transaction_hash == "0x" + "a" * 64


# ==================== Incident Dataclass Tests ====================


class TestIncidentDataclass:
    """Tests de la dataclass Incident."""

    @pytest.mark.unit
    def test_incident_creation_defaults(self):
        """Test creacion de incidente con valores por defecto."""
        incident = Incident(
            id="inc-1",
            title="Test Incident",
            description="Test",
            severity=IncidentSeverity.SEV3,
            status=IncidentStatus.DETECTED,
            detected_at=datetime.utcnow(),
            detected_by="admin@fincore.mx",
        )

        assert incident.affected_contracts == []
        assert incident.related_transactions == []
        assert incident.actions_taken == []
        assert incident.contained_at is None
        assert incident.resolved_at is None


# ==================== Enum Tests ====================


class TestEnums:
    """Tests de enums."""

    @pytest.mark.unit
    def test_alert_severity_values(self):
        """Test valores de AlertSeverity."""
        assert AlertSeverity.CRITICAL.value == "critical"
        assert AlertSeverity.HIGH.value == "high"
        assert AlertSeverity.MEDIUM.value == "medium"
        assert AlertSeverity.LOW.value == "low"
        assert AlertSeverity.INFO.value == "info"

    @pytest.mark.unit
    def test_incident_severity_values(self):
        """Test valores de IncidentSeverity."""
        assert IncidentSeverity.SEV1.value == "sev1"
        assert IncidentSeverity.SEV2.value == "sev2"
        assert IncidentSeverity.SEV3.value == "sev3"
        assert IncidentSeverity.SEV4.value == "sev4"

    @pytest.mark.unit
    def test_incident_status_values(self):
        """Test valores de IncidentStatus."""
        assert IncidentStatus.DETECTED.value == "detected"
        assert IncidentStatus.INVESTIGATING.value == "investigating"
        assert IncidentStatus.CONTAINED.value == "contained"
        assert IncidentStatus.RESOLVED.value == "resolved"
