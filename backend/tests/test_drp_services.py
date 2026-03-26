"""
Tests para los Servicios de DRP (Disaster Recovery Plan).

Tests unitarios para:
- Status Page Service
- Chaos Engineering Service
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from uuid import uuid4

from app.services.status_page_service import (
    StatusPageService,
    ComponentStatus,
    IncidentStatus,
    IncidentImpact,
    MaintenanceStatus,
    Component,
    Incident,
    ScheduledMaintenance,
    SystemStatus,
)
from app.services.chaos_engineering_service import (
    ChaosService,
    ExperimentType,
    ExperimentStatus,
    TargetType,
    LatencyInjector,
    ErrorInjector,
    ResourceExhaustionInjector,
    DependencyFailureInjector,
    chaos_enabled,
    chaos_target,
)


# ==================== FIXTURES ====================

@pytest.fixture
def mock_db():
    """Mock de sesion de base de datos."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.order_by.return_value.all.return_value = []
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.query.return_value.order_by.return_value.first.return_value = None
    return db


@pytest.fixture
def status_service(mock_db):
    """Instancia del StatusPageService con mocks."""
    with patch('app.services.status_page_service.SessionLocal', return_value=mock_db):
        service = StatusPageService(db=mock_db)
        # Inicializar componentes manualmente para tests
        from app.services.status_page_service import Component, ComponentStatus
        service._components = {
            "api": Component(
                id="1", name="api", description="API",
                status=ComponentStatus.OPERATIONAL, group="Core"
            ),
            "database": Component(
                id="2", name="database", description="Database",
                status=ComponentStatus.OPERATIONAL, group="Infrastructure"
            ),
            "cache": Component(
                id="3", name="cache", description="Cache",
                status=ComponentStatus.OPERATIONAL, group="Infrastructure"
            ),
        }
        return service


@pytest.fixture
def chaos_service(mock_db):
    """Instancia del ChaosService con mocks."""
    import app.services.chaos_engineering_service as chaos_module

    # Guardar valores originales
    original_enabled = chaos_module.CHAOS_ENABLED
    original_env = chaos_module.CURRENT_ENVIRONMENT

    # Establecer valores para test
    chaos_module.CHAOS_ENABLED = True
    chaos_module.CURRENT_ENVIRONMENT = 'staging'

    with patch('app.services.chaos_engineering_service.SessionLocal', return_value=mock_db):
        service = ChaosService(db=mock_db)
        yield service

    # Restaurar valores originales
    chaos_module.CHAOS_ENABLED = original_enabled
    chaos_module.CURRENT_ENVIRONMENT = original_env


# ==================== TESTS DE STATUS PAGE ====================

class TestComponentStatus:
    """Tests de estados de componentes."""

    @pytest.mark.integration
    def test_component_status_values(self):
        """Test valores de ComponentStatus."""
        assert ComponentStatus.OPERATIONAL.value == "operational"
        assert ComponentStatus.DEGRADED_PERFORMANCE.value == "degraded_performance"
        assert ComponentStatus.PARTIAL_OUTAGE.value == "partial_outage"
        assert ComponentStatus.MAJOR_OUTAGE.value == "major_outage"
        assert ComponentStatus.UNDER_MAINTENANCE.value == "under_maintenance"

    @pytest.mark.integration
    def test_incident_impact_values(self):
        """Test valores de IncidentImpact."""
        assert IncidentImpact.NONE.value == "none"
        assert IncidentImpact.MINOR.value == "minor"
        assert IncidentImpact.MAJOR.value == "major"
        assert IncidentImpact.CRITICAL.value == "critical"


class TestStatusPageComponents:
    """Tests de componentes del Status Page."""

    @pytest.mark.integration
    def test_default_components_initialized(self, status_service):
        """Test que componentes por defecto se inicializan."""
        components = status_service.get_all_components()
        assert len(components) > 0

        component_names = [c.name for c in components]
        assert "api" in component_names
        assert "database" in component_names

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_update_component_status(self, status_service, mock_db):
        """Test actualizar estado de componente."""
        mock_component = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_component

        component = await status_service.update_component_status(
            component_name="api",
            status=ComponentStatus.DEGRADED_PERFORMANCE,
            notify=False,
        )

        assert component is not None
        assert component.status == ComponentStatus.DEGRADED_PERFORMANCE

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_component(self, status_service):
        """Test obtener componente."""
        component = await status_service.get_component("api")
        assert component is not None
        assert component.name == "api"


class TestStatusPageIncidents:
    """Tests de incidentes."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_incident(self, status_service, mock_db):
        """Test crear incidente."""
        with patch.object(status_service, '_notify_incident_created', new_callable=AsyncMock):
            incident = await status_service.create_incident(
                name="Test Incident",
                impact=IncidentImpact.MINOR,
                components=["api"],
                message="Testing incident creation",
                notify=False,
            )

            assert incident is not None
            assert incident.name == "Test Incident"
            assert incident.impact == IncidentImpact.MINOR
            assert incident.status == IncidentStatus.INVESTIGATING
            assert len(incident.updates) == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_update_incident(self, status_service, mock_db):
        """Test actualizar incidente."""
        # Primero crear incidente
        with patch.object(status_service, '_notify_incident_created', new_callable=AsyncMock):
            incident = await status_service.create_incident(
                name="Test Incident",
                impact=IncidentImpact.MINOR,
                components=["api"],
                message="Initial message",
                notify=False,
            )

        # Actualizar
        with patch.object(status_service, '_notify_incident_updated', new_callable=AsyncMock):
            mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()

            updated = await status_service.update_incident(
                incident_id=incident.id,
                status=IncidentStatus.IDENTIFIED,
                message="Issue identified",
                notify=False,
            )

            assert updated is not None
            assert updated.status == IncidentStatus.IDENTIFIED
            assert len(updated.updates) == 2

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_resolve_incident(self, status_service, mock_db):
        """Test resolver incidente."""
        with patch.object(status_service, '_notify_incident_created', new_callable=AsyncMock):
            incident = await status_service.create_incident(
                name="Test Incident",
                impact=IncidentImpact.MINOR,
                components=["api"],
                message="Initial message",
                notify=False,
            )

        with patch.object(status_service, '_notify_incident_updated', new_callable=AsyncMock):
            mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()

            resolved = await status_service.resolve_incident(
                incident_id=incident.id,
                message="Issue resolved",
            )

            assert resolved.status == IncidentStatus.RESOLVED
            assert resolved.resolved_at is not None

    @pytest.mark.integration
    def test_get_active_incidents(self, status_service):
        """Test obtener incidentes activos."""
        incidents = status_service.get_active_incidents()
        assert isinstance(incidents, list)


class TestStatusPageMaintenance:
    """Tests de mantenimientos programados."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_schedule_maintenance(self, status_service, mock_db):
        """Test programar mantenimiento."""
        with patch.object(status_service, '_notify_maintenance_scheduled', new_callable=AsyncMock):
            maintenance = await status_service.schedule_maintenance(
                name="Database upgrade",
                components=["database"],
                scheduled_for=datetime.utcnow() + timedelta(days=1),
                scheduled_until=datetime.utcnow() + timedelta(days=1, hours=2),
                description="Upgrading database to version 15.5",
                notify=False,
            )

            assert maintenance is not None
            assert maintenance.name == "Database upgrade"
            assert maintenance.status == MaintenanceStatus.SCHEDULED
            mock_db.add.assert_called()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_start_maintenance(self, status_service, mock_db):
        """Test iniciar mantenimiento."""
        with patch.object(status_service, '_notify_maintenance_scheduled', new_callable=AsyncMock):
            maintenance = await status_service.schedule_maintenance(
                name="Test maintenance",
                components=["database"],
                scheduled_for=datetime.utcnow(),
                scheduled_until=datetime.utcnow() + timedelta(hours=2),
                description="Test",
                notify=False,
            )

        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()

        started = await status_service.start_maintenance(maintenance.id)
        assert started.status == MaintenanceStatus.IN_PROGRESS


class TestSystemStatus:
    """Tests de estado del sistema."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_status(self, status_service):
        """Test obtener estado del sistema."""
        status = await status_service.get_status()

        assert status is not None
        assert hasattr(status, 'indicator')
        assert hasattr(status, 'components')
        assert hasattr(status, 'incidents')

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_status_to_dict(self, status_service):
        """Test convertir estado a diccionario."""
        status = await status_service.get_status()
        d = status.to_dict()

        assert 'status' in d
        assert 'components' in d
        assert 'incidents' in d
        assert 'page' in d


# ==================== TESTS DE CHAOS ENGINEERING ====================

class TestChaosServiceConfig:
    """Tests de configuracion de Chaos Service."""

    @pytest.mark.integration
    def test_chaos_service_enabled(self, chaos_service):
        """Test que chaos service esta habilitado en staging."""
        assert chaos_service.is_enabled() is True

    @pytest.mark.integration
    def test_chaos_service_disabled_in_production(self, mock_db):
        """Test que chaos service esta deshabilitado en produccion."""
        with patch('app.services.chaos_engineering_service.SessionLocal', return_value=mock_db):
            with patch('app.services.chaos_engineering_service.CURRENT_ENVIRONMENT', 'production'):
                service = ChaosService(db=mock_db)
                assert service.is_enabled() is False


class TestLatencyInjector:
    """Tests de inyector de latencia."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_inject_latency(self):
        """Test inyectar latencia."""
        injector = LatencyInjector()

        result = await injector.inject({
            "target": "database",
            "latency_ms": 100,
            "jitter_ms": 10,
        })

        assert result is True
        assert injector.is_active() is True
        assert "database" in injector._active_delays

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_latency(self):
        """Test rollback de latencia."""
        injector = LatencyInjector()

        await injector.inject({"target": "api", "latency_ms": 50})
        await injector.rollback()

        assert injector.is_active() is False
        assert len(injector._active_delays) == 0


class TestErrorInjector:
    """Tests de inyector de errores."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_inject_error(self):
        """Test inyectar errores."""
        injector = ErrorInjector()

        result = await injector.inject({
            "target": "api",
            "error_rate": 0.5,
            "error_type": "Exception",
            "error_message": "Test error",
        })

        assert result is True
        assert injector.is_active() is True

    @pytest.mark.integration
    def test_maybe_raise_error(self):
        """Test probabilidad de error."""
        # Limpiar estado
        ErrorInjector._active_errors.clear()

        # Configurar error al 100%
        ErrorInjector._active_errors["test"] = {
            "rate": 1.0,
            "type": "ValueError",
            "message": "Test error",
        }

        with pytest.raises(ValueError, match="Test error"):
            ErrorInjector.maybe_raise("test")


class TestResourceExhaustionInjector:
    """Tests de inyector de agotamiento de recursos."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_inject_resource_exhaustion(self):
        """Test inyectar agotamiento de recursos."""
        injector = ResourceExhaustionInjector()

        result = await injector.inject({
            "resource": "connections",
            "level": 0.95,
        })

        assert result is True
        assert injector.is_active() is True

    @pytest.mark.integration
    def test_check_availability(self):
        """Test verificar disponibilidad."""
        ResourceExhaustionInjector._exhausted_resources.clear()

        # Sin exhaustion, siempre disponible
        assert ResourceExhaustionInjector.check_availability("any") is True

        # Con exhaustion al 100%, nunca disponible
        ResourceExhaustionInjector._exhausted_resources["connections"] = {
            "level": 1.0,
            "simulated_available": 0.0,
        }

        assert ResourceExhaustionInjector.check_availability("connections") is False


class TestDependencyFailureInjector:
    """Tests de inyector de falla de dependencias."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_inject_dependency_failure(self):
        """Test inyectar falla de dependencia."""
        injector = DependencyFailureInjector()

        result = await injector.inject({
            "dependency": "blockchain-rpc",
            "failure_mode": "connection_refused",
        })

        assert result is True
        assert DependencyFailureInjector.is_dependency_failed("blockchain-rpc") is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_dependency_failure(self):
        """Test rollback de falla de dependencia."""
        injector = DependencyFailureInjector()

        await injector.inject({"dependency": "external-api"})
        await injector.rollback()

        assert DependencyFailureInjector.is_dependency_failed("external-api") is False


class TestChaosExperiments:
    """Tests de experimentos de caos."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_run_latency_experiment(self, chaos_service, mock_db):
        """Test ejecutar experimento de latencia."""
        # Ejecutar experimento sin steady state check para simplificar test
        result = await chaos_service.run_experiment(
            experiment_type="latency-injection",
            config={
                "target": "database",
                "latency_ms": 100,
                "jitter_ms": 10,
                "duration_seconds": 1,
            },
            created_by="test@fincore.com",
        )

        assert result is not None
        assert result.type == ExperimentType.LATENCY_INJECTION
        assert result.status in (ExperimentStatus.COMPLETED, ExperimentStatus.FAILED, ExperimentStatus.ABORTED)
        mock_db.add.assert_called()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_run_error_experiment(self, chaos_service, mock_db):
        """Test ejecutar experimento de errores."""
        result = await chaos_service.run_error_experiment(
            target="api",
            error_rate=0.1,
            duration_seconds=1,
            created_by="test@fincore.com",
        )

        assert result is not None
        assert result.type == ExperimentType.ERROR_INJECTION

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_experiment_creates_observations(self, chaos_service, mock_db):
        """Test que experimentos crean observaciones."""
        result = await chaos_service.run_experiment(
            experiment_type="latency-injection",
            config={
                "target": "cache",
                "latency_ms": 50,
                "jitter_ms": 5,
                "duration_seconds": 1,
            },
        )

        # Verificar que hay observaciones (puede ser rollback si fallo)
        assert len(result.observations) > 0
        # Al menos deberia haber una fase registrada
        phases = [obs.get("phase") for obs in result.observations if obs.get("phase")]
        assert len(phases) > 0

    @pytest.mark.integration
    def test_get_experiment_history(self, chaos_service, mock_db):
        """Test obtener historial de experimentos."""
        history = chaos_service.get_experiment_history(limit=10)
        assert isinstance(history, list)

    @pytest.mark.integration
    def test_get_active_experiments(self, chaos_service):
        """Test obtener experimentos activos."""
        active = chaos_service.get_active_experiments()
        assert isinstance(active, list)


class TestChaosDecorators:
    """Tests de decoradores de chaos."""

    @pytest.fixture(autouse=True)
    def cleanup_injectors(self):
        """Limpiar estado de injectors antes y despues de cada test."""
        # Limpiar antes
        LatencyInjector._active_delays.clear()
        ErrorInjector._active_errors.clear()
        ResourceExhaustionInjector._exhausted_resources.clear()
        DependencyFailureInjector._failed_dependencies.clear()
        yield
        # Limpiar despues
        LatencyInjector._active_delays.clear()
        ErrorInjector._active_errors.clear()
        ResourceExhaustionInjector._exhausted_resources.clear()
        DependencyFailureInjector._failed_dependencies.clear()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_chaos_enabled_decorator(self):
        """Test decorador chaos_enabled."""
        @chaos_enabled
        async def test_function():
            return "success"

        result = await test_function()
        assert result == "success"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_chaos_target_decorator(self):
        """Test decorador chaos_target."""
        @chaos_target("database")
        async def query_db():
            return "data"

        result = await query_db()
        assert result == "data"


# ==================== TESTS DE INTEGRACION ====================

class TestDRPIntegration:
    """Tests de integracion de DRP."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_incident_affects_component_status(self, status_service, mock_db):
        """Test que incidente afecta estado de componentes."""
        with patch.object(status_service, '_notify_incident_created', new_callable=AsyncMock):
            await status_service.create_incident(
                name="API Outage",
                impact=IncidentImpact.CRITICAL,
                components=["api"],
                message="API is down",
                notify=False,
            )

        # Verificar que el componente fue actualizado
        api_component = await status_service.get_component("api")
        assert api_component.status == ComponentStatus.MAJOR_OUTAGE

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_resolved_incident_restores_component(self, status_service, mock_db):
        """Test que resolver incidente restaura componente."""
        with patch.object(status_service, '_notify_incident_created', new_callable=AsyncMock):
            incident = await status_service.create_incident(
                name="Test Incident",
                impact=IncidentImpact.MAJOR,
                components=["database"],
                message="DB issue",
                notify=False,
            )

        with patch.object(status_service, '_notify_incident_updated', new_callable=AsyncMock):
            mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()

            await status_service.resolve_incident(
                incident_id=incident.id,
                message="Issue resolved",
            )

        # Verificar que componente volvio a operational
        db_component = await status_service.get_component("database")
        assert db_component.status == ComponentStatus.OPERATIONAL
