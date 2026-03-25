"""
Servicio de Notificaciones.
Gestiona creacion, envio y persistencia de notificaciones.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_

from app.models.notification import (
    Notification,
    NotificationPreference,
    NotificationType,
    NotificationPriority
)
from app.core.websocket import (
    manager,
    notify_user,
    notify_admins,
    notify_all,
    WebSocketMessage,
    NotificationType as WSNotificationType,
    NotificationPriority as WSNotificationPriority
)


class NotificationService:
    """Servicio para gestionar notificaciones."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_notification(
        self,
        user_id: UUID,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        data: Optional[Dict[str, Any]] = None,
        expires_in_days: Optional[int] = None,
        send_ws: bool = True
    ) -> Notification:
        """
        Crea una nueva notificacion y la envia por WebSocket si el usuario esta conectado.
        """
        # Verificar preferencias del usuario
        preferences = await self.get_user_preferences(user_id)
        if preferences and not self._should_notify(preferences, notification_type, priority):
            return None

        # Crear notificacion en DB
        notification = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            priority=priority,
            data=data,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None
        )

        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)

        # Enviar por WebSocket si esta habilitado
        if send_ws and (not preferences or preferences.enable_websocket):
            sent = await notify_user(
                user_id=str(user_id),
                notification_type=WSNotificationType(notification_type.value),
                title=title,
                message=message,
                priority=WSNotificationPriority(priority.value),
                data=data
            )

            if sent > 0:
                notification.delivered_via_ws = True
                notification.delivered_at = datetime.utcnow()
                await self.db.commit()

        return notification

    def _should_notify(
        self,
        preferences: NotificationPreference,
        notification_type: NotificationType,
        priority: NotificationPriority
    ) -> bool:
        """Verifica si se debe enviar la notificacion segun preferencias."""
        # Verificar prioridad minima
        priority_order = {
            NotificationPriority.LOW: 0,
            NotificationPriority.MEDIUM: 1,
            NotificationPriority.HIGH: 2,
            NotificationPriority.CRITICAL: 3
        }

        if priority_order.get(priority, 0) < priority_order.get(preferences.min_priority, 0):
            return False

        # Verificar tipo de notificacion
        type_value = notification_type.value
        if type_value.startswith("audit_") and not preferences.audit_notifications:
            return False
        if type_value.startswith("compliance_") or type_value.startswith("kyc_") or type_value.startswith("risk_"):
            if not preferences.compliance_notifications:
                return False
        if type_value.startswith("investment_") or type_value.startswith("dividend_"):
            if not preferences.investment_notifications:
                return False
        if type_value.startswith("project_"):
            if not preferences.project_notifications:
                return False
        if type_value.startswith("system_"):
            if not preferences.system_notifications:
                return False

        return True

    async def get_user_notifications(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
        notification_type: Optional[NotificationType] = None
    ) -> List[Notification]:
        """Obtiene las notificaciones de un usuario."""
        query = select(Notification).where(Notification.user_id == user_id)

        if unread_only:
            query = query.where(Notification.is_read == False)

        if notification_type:
            query = query.where(Notification.notification_type == notification_type)

        query = query.order_by(Notification.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_unread_count(self, user_id: UUID) -> int:
        """Obtiene el conteo de notificaciones no leidas."""
        query = select(func.count(Notification.id)).where(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False
            )
        )
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def mark_as_read(self, notification_id: UUID, user_id: UUID) -> bool:
        """Marca una notificacion como leida."""
        query = update(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        ).values(is_read=True, read_at=datetime.utcnow())

        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount > 0

    async def mark_all_as_read(self, user_id: UUID) -> int:
        """Marca todas las notificaciones de un usuario como leidas."""
        query = update(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False
            )
        ).values(is_read=True, read_at=datetime.utcnow())

        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount

    async def delete_notification(self, notification_id: UUID, user_id: UUID) -> bool:
        """Elimina una notificacion."""
        query = delete(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        )
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount > 0

    async def delete_old_notifications(self, days: int = 30) -> int:
        """Elimina notificaciones antiguas."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = delete(Notification).where(
            or_(
                Notification.created_at < cutoff_date,
                and_(
                    Notification.expires_at.isnot(None),
                    Notification.expires_at < datetime.utcnow()
                )
            )
        )
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount

    async def get_user_preferences(self, user_id: UUID) -> Optional[NotificationPreference]:
        """Obtiene las preferencias de notificacion de un usuario."""
        query = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_user_preferences(
        self,
        user_id: UUID,
        **preferences
    ) -> NotificationPreference:
        """Actualiza las preferencias de notificacion de un usuario."""
        existing = await self.get_user_preferences(user_id)

        if existing:
            for key, value in preferences.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        else:
            new_prefs = NotificationPreference(user_id=user_id, **preferences)
            self.db.add(new_prefs)
            await self.db.commit()
            await self.db.refresh(new_prefs)
            return new_prefs


# Funciones helper para uso desde otros modulos
async def create_audit_notification(
    db: AsyncSession,
    user_id: UUID,
    audit_type: str,  # "started", "completed", "failed", "finding"
    title: str,
    message: str,
    data: Optional[Dict] = None,
    priority: NotificationPriority = NotificationPriority.MEDIUM
) -> Optional[Notification]:
    """Helper para crear notificaciones de auditoria."""
    service = NotificationService(db)

    type_map = {
        "started": NotificationType.AUDIT_STARTED,
        "completed": NotificationType.AUDIT_COMPLETED,
        "failed": NotificationType.AUDIT_FAILED,
        "finding": NotificationType.AUDIT_FINDING
    }

    notification_type = type_map.get(audit_type, NotificationType.INFO)

    return await service.create_notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        priority=priority,
        data=data
    )


async def create_compliance_notification(
    db: AsyncSession,
    user_id: UUID,
    alert_type: str,
    title: str,
    message: str,
    data: Optional[Dict] = None
) -> Optional[Notification]:
    """Helper para crear notificaciones de compliance."""
    service = NotificationService(db)

    return await service.create_notification(
        user_id=user_id,
        notification_type=NotificationType.COMPLIANCE_ALERT,
        title=title,
        message=message,
        priority=NotificationPriority.HIGH,
        data=data
    )


async def create_system_notification(
    db: AsyncSession,
    user_id: UUID,
    title: str,
    message: str,
    priority: NotificationPriority = NotificationPriority.MEDIUM,
    data: Optional[Dict] = None
) -> Optional[Notification]:
    """Helper para crear notificaciones del sistema."""
    service = NotificationService(db)

    return await service.create_notification(
        user_id=user_id,
        notification_type=NotificationType.SYSTEM_ALERT,
        title=title,
        message=message,
        priority=priority,
        data=data
    )
