"""
Endpoints de Notificaciones y WebSocket.
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.api.v1.endpoints.auth import get_current_user
from app.core.websocket import manager, NotificationType as WSNotificationType, NotificationPriority as WSNotificationPriority
from app.models.user import User
from app.models.notification import NotificationType, NotificationPriority
from app.services.notification_service import NotificationService

router = APIRouter()


# Schemas
class NotificationResponse(BaseModel):
    """Respuesta de notificacion."""
    id: str
    notification_type: str
    priority: str
    title: str
    message: str
    data: Optional[dict] = None
    is_read: bool
    read_at: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Lista de notificaciones con metadatos."""
    notifications: List[NotificationResponse]
    total_unread: int
    has_more: bool


class NotificationPreferencesRequest(BaseModel):
    """Request para actualizar preferencias."""
    audit_notifications: Optional[bool] = None
    compliance_notifications: Optional[bool] = None
    investment_notifications: Optional[bool] = None
    project_notifications: Optional[bool] = None
    system_notifications: Optional[bool] = None
    min_priority: Optional[str] = None
    enable_websocket: Optional[bool] = None
    enable_email: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None


class NotificationPreferencesResponse(BaseModel):
    """Respuesta de preferencias."""
    audit_notifications: bool
    compliance_notifications: bool
    investment_notifications: bool
    project_notifications: bool
    system_notifications: bool
    min_priority: str
    enable_websocket: bool
    enable_email: bool
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None


class MarkReadRequest(BaseModel):
    """Request para marcar como leida."""
    notification_ids: Optional[List[str]] = None
    mark_all: bool = False


class WebSocketStats(BaseModel):
    """Estadisticas de WebSocket."""
    connected_users: int
    total_connections: int
    user_connected: bool


# WebSocket endpoint
@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint para notificaciones en tiempo real.

    Conexion: ws://host/api/v1/notifications/ws?token=<jwt_token>

    El servidor envia mensajes JSON con formato:
    {
        "type": "notification",
        "notification_type": "audit_completed",
        "title": "Auditoria Completada",
        "message": "...",
        "priority": "high",
        "data": {...},
        "timestamp": "...",
        "id": "..."
    }
    """
    # Verificar token
    if not token:
        await websocket.close(code=4001, reason="Token requerido")
        return

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4002, reason="Token invalido")
            return
    except Exception as e:
        await websocket.close(code=4003, reason=f"Error de autenticacion: {str(e)}")
        return

    # Conectar
    await manager.connect(websocket, user_id)

    # Agregar a grupos segun rol (obtener de token)
    user_role = payload.get("rol")
    if user_role == "Admin":
        await manager.add_to_group(user_id, "admins")

    try:
        while True:
            # Recibir mensajes del cliente (para keep-alive o comandos)
            data = await websocket.receive_text()

            # Procesar comandos del cliente
            if data == "ping":
                await websocket.send_text('{"type": "pong"}')
            elif data == "status":
                await websocket.send_text(f'{{"type": "status", "connected": true, "user_id": "{user_id}"}}')

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        if user_role == "Admin":
            await manager.remove_from_group(user_id, "admins")


# REST endpoints
@router.get("/notifications", response_model=NotificationListResponse)
async def get_notifications(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    notification_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene las notificaciones del usuario actual.
    """
    service = NotificationService(db)

    # Convertir tipo si se proporciona
    notif_type = None
    if notification_type:
        try:
            notif_type = NotificationType(notification_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Tipo de notificacion invalido: {notification_type}")

    notifications = await service.get_user_notifications(
        user_id=current_user.id,
        limit=limit + 1,  # +1 para saber si hay mas
        offset=offset,
        unread_only=unread_only,
        notification_type=notif_type
    )

    unread_count = await service.get_unread_count(current_user.id)

    has_more = len(notifications) > limit
    if has_more:
        notifications = notifications[:-1]

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=str(n.id),
                notification_type=n.notification_type.value,
                priority=n.priority.value,
                title=n.title,
                message=n.message,
                data=n.data,
                is_read=n.is_read,
                read_at=n.read_at.isoformat() if n.read_at else None,
                created_at=n.created_at.isoformat()
            )
            for n in notifications
        ],
        total_unread=unread_count,
        has_more=has_more
    )


@router.get("/notifications/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene el conteo de notificaciones no leidas."""
    service = NotificationService(db)
    count = await service.get_unread_count(current_user.id)
    return {"unread_count": count}


@router.post("/notifications/mark-read")
async def mark_notifications_read(
    request: MarkReadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Marca notificaciones como leidas.
    Puede marcar una lista especifica o todas.
    """
    service = NotificationService(db)

    if request.mark_all:
        count = await service.mark_all_as_read(current_user.id)
        return {"marked_count": count}

    if not request.notification_ids:
        raise HTTPException(status_code=400, detail="Debe proporcionar notification_ids o mark_all=true")

    marked_count = 0
    for notif_id in request.notification_ids:
        try:
            if await service.mark_as_read(UUID(notif_id), current_user.id):
                marked_count += 1
        except ValueError:
            continue

    return {"marked_count": marked_count}


@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Elimina una notificacion."""
    service = NotificationService(db)

    try:
        deleted = await service.delete_notification(UUID(notification_id), current_user.id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de notificacion invalido")

    if not deleted:
        raise HTTPException(status_code=404, detail="Notificacion no encontrada")

    return {"deleted": True}


@router.get("/notifications/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene las preferencias de notificacion del usuario."""
    service = NotificationService(db)
    prefs = await service.get_user_preferences(current_user.id)

    if not prefs:
        # Retornar valores por defecto
        return NotificationPreferencesResponse(
            audit_notifications=True,
            compliance_notifications=True,
            investment_notifications=True,
            project_notifications=True,
            system_notifications=True,
            min_priority="low",
            enable_websocket=True,
            enable_email=False
        )

    return NotificationPreferencesResponse(
        audit_notifications=prefs.audit_notifications,
        compliance_notifications=prefs.compliance_notifications,
        investment_notifications=prefs.investment_notifications,
        project_notifications=prefs.project_notifications,
        system_notifications=prefs.system_notifications,
        min_priority=prefs.min_priority.value,
        enable_websocket=prefs.enable_websocket,
        enable_email=prefs.enable_email,
        quiet_hours_start=prefs.quiet_hours_start,
        quiet_hours_end=prefs.quiet_hours_end
    )


@router.put("/notifications/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    request: NotificationPreferencesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualiza las preferencias de notificacion."""
    service = NotificationService(db)

    # Convertir min_priority si se proporciona
    update_data = request.dict(exclude_none=True)
    if "min_priority" in update_data:
        try:
            update_data["min_priority"] = NotificationPriority(update_data["min_priority"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Prioridad invalida")

    prefs = await service.update_user_preferences(current_user.id, **update_data)

    return NotificationPreferencesResponse(
        audit_notifications=prefs.audit_notifications,
        compliance_notifications=prefs.compliance_notifications,
        investment_notifications=prefs.investment_notifications,
        project_notifications=prefs.project_notifications,
        system_notifications=prefs.system_notifications,
        min_priority=prefs.min_priority.value,
        enable_websocket=prefs.enable_websocket,
        enable_email=prefs.enable_email,
        quiet_hours_start=prefs.quiet_hours_start,
        quiet_hours_end=prefs.quiet_hours_end
    )


@router.get("/notifications/ws-stats", response_model=WebSocketStats)
async def get_websocket_stats(
    current_user: User = Depends(get_current_user)
):
    """Obtiene estadisticas de conexiones WebSocket."""
    return WebSocketStats(
        connected_users=len(manager.get_connected_users()),
        total_connections=manager.get_connection_count(),
        user_connected=manager.is_user_connected(str(current_user.id))
    )


# Endpoint para testing/admin - enviar notificacion
@router.post("/notifications/test", include_in_schema=False)
async def send_test_notification(
    title: str = Query(...),
    message: str = Query(...),
    priority: str = Query("medium"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint de prueba para enviar una notificacion.
    Solo para desarrollo/testing.
    """
    if current_user.rol.value != "Admin":
        raise HTTPException(status_code=403, detail="Solo administradores")

    service = NotificationService(db)

    try:
        prio = NotificationPriority(priority)
    except ValueError:
        prio = NotificationPriority.MEDIUM

    notification = await service.create_notification(
        user_id=current_user.id,
        notification_type=NotificationType.INFO,
        title=title,
        message=message,
        priority=prio
    )

    return {
        "sent": notification is not None,
        "notification_id": str(notification.id) if notification else None
    }
