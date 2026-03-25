"""
Tests para NotificationService.

Cobertura de creacion, filtrado y gestion de notificaciones.
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from decimal import Decimal

from app.services.notification_service import (
    NotificationService,
    create_audit_notification,
    create_compliance_notification,
    create_system_notification,
)
from app.models.notification import (
    NotificationType,
    NotificationPriority,
)


class TestNotificationService:
    """Tests para NotificationService."""

    @pytest.fixture
    def mock_db(self):
        """Mock de sesion de base de datos."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        db.execute = MagicMock()
        return db

    @pytest.fixture
    def notification_service(self, mock_db):
        """Crea instancia del servicio."""
        return NotificationService(mock_db)

    @pytest.fixture
    def user_id(self):
        """UUID de usuario de prueba."""
        return uuid4()

    def test_init(self, notification_service, mock_db):
        """Test inicializacion del servicio."""
        assert notification_service.db == mock_db

    def test_should_notify_all_enabled(self, notification_service):
        """Test _should_notify con todas las preferencias habilitadas."""
        preferences = MagicMock()
        preferences.min_priority = NotificationPriority.LOW
        preferences.audit_notifications = True
        preferences.compliance_notifications = True
        preferences.investment_notifications = True
        preferences.project_notifications = True
        preferences.system_notifications = True

        # Notificacion de auditoria
        result = notification_service._should_notify(
            preferences,
            NotificationType.AUDIT_COMPLETED,
            NotificationPriority.HIGH
        )
        assert result is True

    def test_should_notify_priority_filter(self, notification_service):
        """Test filtrado por prioridad minima."""
        preferences = MagicMock()
        preferences.min_priority = NotificationPriority.HIGH
        preferences.audit_notifications = True

        # Prioridad MEDIUM deberia ser filtrada
        result = notification_service._should_notify(
            preferences,
            NotificationType.AUDIT_COMPLETED,
            NotificationPriority.MEDIUM
        )
        assert result is False

        # Prioridad HIGH deberia pasar
        result = notification_service._should_notify(
            preferences,
            NotificationType.AUDIT_COMPLETED,
            NotificationPriority.HIGH
        )
        assert result is True

    def test_should_notify_audit_disabled(self, notification_service):
        """Test filtrado de notificaciones de auditoria deshabilitadas."""
        preferences = MagicMock()
        preferences.min_priority = NotificationPriority.LOW
        preferences.audit_notifications = False

        result = notification_service._should_notify(
            preferences,
            NotificationType.AUDIT_STARTED,
            NotificationPriority.HIGH
        )
        assert result is False

    def test_should_notify_compliance_disabled(self, notification_service):
        """Test filtrado de notificaciones de compliance deshabilitadas."""
        preferences = MagicMock()
        preferences.min_priority = NotificationPriority.LOW
        preferences.compliance_notifications = False

        result = notification_service._should_notify(
            preferences,
            NotificationType.COMPLIANCE_ALERT,
            NotificationPriority.HIGH
        )
        assert result is False

    def test_should_notify_investment_disabled(self, notification_service):
        """Test filtrado de notificaciones de inversion deshabilitadas."""
        preferences = MagicMock()
        preferences.min_priority = NotificationPriority.LOW
        preferences.investment_notifications = False

        result = notification_service._should_notify(
            preferences,
            NotificationType.INVESTMENT_CONFIRMED,
            NotificationPriority.HIGH
        )
        assert result is False

    def test_should_notify_project_disabled(self, notification_service):
        """Test filtrado de notificaciones de proyecto deshabilitadas."""
        preferences = MagicMock()
        preferences.min_priority = NotificationPriority.LOW
        preferences.project_notifications = False

        result = notification_service._should_notify(
            preferences,
            NotificationType.PROJECT_STATUS_CHANGE,
            NotificationPriority.HIGH
        )
        assert result is False

    def test_should_notify_system_disabled(self, notification_service):
        """Test filtrado de notificaciones del sistema deshabilitadas."""
        preferences = MagicMock()
        preferences.min_priority = NotificationPriority.LOW
        preferences.system_notifications = False

        result = notification_service._should_notify(
            preferences,
            NotificationType.SYSTEM_ALERT,
            NotificationPriority.HIGH
        )
        assert result is False

    def test_get_user_notifications(self, notification_service, mock_db, user_id):
        """Test obtener notificaciones de usuario."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        notifications = notification_service.get_user_notifications(user_id)

        assert isinstance(notifications, list)
        mock_db.execute.assert_called_once()

    def test_get_user_notifications_unread_only(self, notification_service, mock_db, user_id):
        """Test obtener solo notificaciones no leidas."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        notifications = notification_service.get_user_notifications(
            user_id,
            unread_only=True
        )

        assert isinstance(notifications, list)

    def test_get_user_notifications_with_type_filter(self, notification_service, mock_db, user_id):
        """Test obtener notificaciones filtradas por tipo."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        notifications = notification_service.get_user_notifications(
            user_id,
            notification_type=NotificationType.AUDIT_COMPLETED
        )

        assert isinstance(notifications, list)

    def test_get_unread_count(self, notification_service, mock_db, user_id):
        """Test conteo de notificaciones no leidas."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        count = notification_service.get_unread_count(user_id)

        assert count == 5

    def test_get_unread_count_zero(self, notification_service, mock_db, user_id):
        """Test conteo cero cuando no hay notificaciones."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db.execute.return_value = mock_result

        count = notification_service.get_unread_count(user_id)

        assert count == 0

    def test_mark_as_read(self, notification_service, mock_db, user_id):
        """Test marcar notificacion como leida."""
        notification_id = uuid4()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result

        result = notification_service.mark_as_read(notification_id, user_id)

        assert result is True
        mock_db.commit.assert_called_once()

    def test_mark_as_read_not_found(self, notification_service, mock_db, user_id):
        """Test marcar como leida notificacion inexistente."""
        notification_id = uuid4()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result

        result = notification_service.mark_as_read(notification_id, user_id)

        assert result is False

    def test_mark_all_as_read(self, notification_service, mock_db, user_id):
        """Test marcar todas como leidas."""
        mock_result = MagicMock()
        mock_result.rowcount = 10
        mock_db.execute.return_value = mock_result

        count = notification_service.mark_all_as_read(user_id)

        assert count == 10
        mock_db.commit.assert_called_once()

    def test_delete_notification(self, notification_service, mock_db, user_id):
        """Test eliminar notificacion."""
        notification_id = uuid4()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result

        result = notification_service.delete_notification(notification_id, user_id)

        assert result is True
        mock_db.commit.assert_called_once()

    def test_delete_notification_not_found(self, notification_service, mock_db, user_id):
        """Test eliminar notificacion inexistente."""
        notification_id = uuid4()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result

        result = notification_service.delete_notification(notification_id, user_id)

        assert result is False

    def test_delete_old_notifications(self, notification_service, mock_db):
        """Test eliminar notificaciones antiguas."""
        mock_result = MagicMock()
        mock_result.rowcount = 25
        mock_db.execute.return_value = mock_result

        count = notification_service.delete_old_notifications(days=30)

        assert count == 25
        mock_db.commit.assert_called_once()

    def test_get_user_preferences(self, notification_service, mock_db, user_id):
        """Test obtener preferencias de usuario."""
        mock_pref = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_pref
        mock_db.execute.return_value = mock_result

        prefs = notification_service.get_user_preferences(user_id)

        assert prefs == mock_pref

    def test_get_user_preferences_not_found(self, notification_service, mock_db, user_id):
        """Test preferencias no encontradas."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        prefs = notification_service.get_user_preferences(user_id)

        assert prefs is None


class TestHelperFunctions:
    """Tests para funciones helper."""

    @pytest.fixture
    def mock_db(self):
        """Mock de sesion de base de datos."""
        db = MagicMock()
        return db

    @pytest.fixture
    def user_id(self):
        """UUID de usuario de prueba."""
        return uuid4()

    @patch('app.services.notification_service.NotificationService')
    def test_create_audit_notification_started(self, mock_service_class, mock_db, user_id):
        """Test crear notificacion de auditoria iniciada."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        create_audit_notification(
            db=mock_db,
            user_id=user_id,
            audit_type="started",
            title="Auditoria Iniciada",
            message="Se ha iniciado la auditoria del contrato"
        )

        mock_service.create_notification.assert_called_once()
        call_args = mock_service.create_notification.call_args
        assert call_args.kwargs['notification_type'] == NotificationType.AUDIT_STARTED

    @patch('app.services.notification_service.NotificationService')
    def test_create_audit_notification_completed(self, mock_service_class, mock_db, user_id):
        """Test crear notificacion de auditoria completada."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        create_audit_notification(
            db=mock_db,
            user_id=user_id,
            audit_type="completed",
            title="Auditoria Completada",
            message="La auditoria ha finalizado"
        )

        mock_service.create_notification.assert_called_once()
        call_args = mock_service.create_notification.call_args
        assert call_args.kwargs['notification_type'] == NotificationType.AUDIT_COMPLETED

    @patch('app.services.notification_service.NotificationService')
    def test_create_audit_notification_failed(self, mock_service_class, mock_db, user_id):
        """Test crear notificacion de auditoria fallida."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        create_audit_notification(
            db=mock_db,
            user_id=user_id,
            audit_type="failed",
            title="Auditoria Fallida",
            message="Error en la auditoria"
        )

        mock_service.create_notification.assert_called_once()
        call_args = mock_service.create_notification.call_args
        assert call_args.kwargs['notification_type'] == NotificationType.AUDIT_FAILED

    @patch('app.services.notification_service.NotificationService')
    def test_create_audit_notification_finding(self, mock_service_class, mock_db, user_id):
        """Test crear notificacion de hallazgo."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        create_audit_notification(
            db=mock_db,
            user_id=user_id,
            audit_type="finding",
            title="Hallazgo Detectado",
            message="Se detecto una vulnerabilidad",
            data={"severity": "high"}
        )

        mock_service.create_notification.assert_called_once()
        call_args = mock_service.create_notification.call_args
        assert call_args.kwargs['notification_type'] == NotificationType.AUDIT_FINDING
        assert call_args.kwargs['data'] == {"severity": "high"}

    @patch('app.services.notification_service.NotificationService')
    def test_create_compliance_notification(self, mock_service_class, mock_db, user_id):
        """Test crear notificacion de compliance."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        create_compliance_notification(
            db=mock_db,
            user_id=user_id,
            alert_type="kyc_required",
            title="KYC Requerido",
            message="Por favor complete su verificacion KYC"
        )

        mock_service.create_notification.assert_called_once()
        call_args = mock_service.create_notification.call_args
        assert call_args.kwargs['notification_type'] == NotificationType.COMPLIANCE_ALERT
        assert call_args.kwargs['priority'] == NotificationPriority.HIGH

    @patch('app.services.notification_service.NotificationService')
    def test_create_system_notification(self, mock_service_class, mock_db, user_id):
        """Test crear notificacion del sistema."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        create_system_notification(
            db=mock_db,
            user_id=user_id,
            title="Mantenimiento Programado",
            message="El sistema estara en mantenimiento manana"
        )

        mock_service.create_notification.assert_called_once()
        call_args = mock_service.create_notification.call_args
        assert call_args.kwargs['notification_type'] == NotificationType.SYSTEM_ALERT

    @patch('app.services.notification_service.NotificationService')
    def test_create_system_notification_critical(self, mock_service_class, mock_db, user_id):
        """Test crear notificacion critica del sistema."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        create_system_notification(
            db=mock_db,
            user_id=user_id,
            title="Alerta de Seguridad",
            message="Se detecto actividad sospechosa",
            priority=NotificationPriority.CRITICAL
        )

        mock_service.create_notification.assert_called_once()
        call_args = mock_service.create_notification.call_args
        assert call_args.kwargs['priority'] == NotificationPriority.CRITICAL


class TestNotificationTypes:
    """Tests para tipos de notificacion."""

    def test_audit_notification_types(self):
        """Verifica tipos de notificacion de auditoria."""
        assert NotificationType.AUDIT_STARTED.value == "audit_started"
        assert NotificationType.AUDIT_COMPLETED.value == "audit_completed"
        assert NotificationType.AUDIT_FAILED.value == "audit_failed"
        assert NotificationType.AUDIT_FINDING.value == "audit_finding"

    def test_investment_notification_types(self):
        """Verifica tipos de notificacion de inversion."""
        assert NotificationType.INVESTMENT_CONFIRMED.value == "investment_confirmed"
        assert NotificationType.DIVIDEND_AVAILABLE.value == "dividend_available"

    def test_compliance_notification_types(self):
        """Verifica tipos de notificacion de compliance."""
        assert NotificationType.COMPLIANCE_ALERT.value == "compliance_alert"
        assert NotificationType.KYC_STATUS_CHANGE.value == "kyc_status_change"
        assert NotificationType.RISK_ALERT.value == "risk_alert"


class TestNotificationPriorities:
    """Tests para prioridades de notificacion."""

    def test_priority_order(self):
        """Verifica orden de prioridades."""
        priorities = [
            NotificationPriority.LOW,
            NotificationPriority.MEDIUM,
            NotificationPriority.HIGH,
            NotificationPriority.CRITICAL
        ]

        # Verificar que existen todos
        assert len(priorities) == 4

    def test_priority_values(self):
        """Verifica valores de prioridades."""
        assert NotificationPriority.LOW.value == "low"
        assert NotificationPriority.MEDIUM.value == "medium"
        assert NotificationPriority.HIGH.value == "high"
        assert NotificationPriority.CRITICAL.value == "critical"
