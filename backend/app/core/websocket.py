"""
WebSocket Manager para notificaciones en tiempo real.
Gestiona conexiones de usuarios y envio de mensajes.
"""
import json
import asyncio
from typing import Dict, List, Optional, Set, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel


class NotificationType(str, Enum):
    """Tipos de notificacion."""
    # Auditoria
    AUDIT_STARTED = "audit_started"
    AUDIT_COMPLETED = "audit_completed"
    AUDIT_FAILED = "audit_failed"
    AUDIT_FINDING = "audit_finding"

    # Compliance
    COMPLIANCE_ALERT = "compliance_alert"
    KYC_STATUS_CHANGE = "kyc_status_change"
    RISK_ALERT = "risk_alert"

    # Inversiones
    INVESTMENT_RECEIVED = "investment_received"
    INVESTMENT_CONFIRMED = "investment_confirmed"
    DIVIDEND_AVAILABLE = "dividend_available"

    # Proyectos
    PROJECT_STATUS_CHANGE = "project_status_change"
    PROJECT_MILESTONE = "project_milestone"

    # Sistema
    SYSTEM_ALERT = "system_alert"
    SYSTEM_MAINTENANCE = "system_maintenance"

    # General
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class NotificationPriority(str, Enum):
    """Prioridad de notificacion."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class WebSocketMessage:
    """Mensaje WebSocket."""
    type: str
    notification_type: NotificationType
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.MEDIUM
    data: Optional[Dict[str, Any]] = None
    timestamp: str = None
    id: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
        if self.id is None:
            import uuid
            self.id = str(uuid.uuid4())

    def to_json(self) -> str:
        return json.dumps(asdict(self))


class ConnectionManager:
    """
    Gestor de conexiones WebSocket.
    Mantiene un registro de conexiones activas por usuario.
    """

    def __init__(self):
        # user_id -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # WebSocket -> user_id
        self.connection_user: Dict[WebSocket, str] = {}
        # Grupos de usuarios (roles, proyectos, etc.)
        self.groups: Dict[str, Set[str]] = {}
        # Lock para operaciones thread-safe
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """Acepta una nueva conexion WebSocket."""
        await websocket.accept()

        async with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()

            self.active_connections[user_id].add(websocket)
            self.connection_user[websocket] = user_id

        # Enviar mensaje de bienvenida
        await self.send_personal_message(
            WebSocketMessage(
                type="connection",
                notification_type=NotificationType.INFO,
                title="Conectado",
                message="Conexion WebSocket establecida",
                priority=NotificationPriority.LOW
            ),
            user_id
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Desconecta un WebSocket."""
        async with self._lock:
            user_id = self.connection_user.get(websocket)
            if user_id:
                if user_id in self.active_connections:
                    self.active_connections[user_id].discard(websocket)
                    if not self.active_connections[user_id]:
                        del self.active_connections[user_id]
                del self.connection_user[websocket]

    async def add_to_group(self, user_id: str, group: str) -> None:
        """Agrega un usuario a un grupo."""
        async with self._lock:
            if group not in self.groups:
                self.groups[group] = set()
            self.groups[group].add(user_id)

    async def remove_from_group(self, user_id: str, group: str) -> None:
        """Remueve un usuario de un grupo."""
        async with self._lock:
            if group in self.groups:
                self.groups[group].discard(user_id)
                if not self.groups[group]:
                    del self.groups[group]

    async def send_personal_message(
        self,
        message: WebSocketMessage,
        user_id: str
    ) -> int:
        """
        Envia un mensaje a todas las conexiones de un usuario.
        Retorna el numero de conexiones alcanzadas.
        """
        sent = 0
        connections = self.active_connections.get(user_id, set()).copy()

        for websocket in connections:
            try:
                await websocket.send_text(message.to_json())
                sent += 1
            except Exception:
                # Conexion cerrada, limpiar
                await self.disconnect(websocket)

        return sent

    async def send_to_group(
        self,
        message: WebSocketMessage,
        group: str
    ) -> int:
        """
        Envia un mensaje a todos los usuarios de un grupo.
        Retorna el numero de conexiones alcanzadas.
        """
        sent = 0
        user_ids = self.groups.get(group, set()).copy()

        for user_id in user_ids:
            sent += await self.send_personal_message(message, user_id)

        return sent

    async def broadcast(self, message: WebSocketMessage) -> int:
        """
        Envia un mensaje a todas las conexiones activas.
        Retorna el numero de conexiones alcanzadas.
        """
        sent = 0

        for user_id in list(self.active_connections.keys()):
            sent += await self.send_personal_message(message, user_id)

        return sent

    async def send_to_admins(self, message: WebSocketMessage) -> int:
        """Envia un mensaje solo a administradores."""
        return await self.send_to_group(message, "admins")

    def get_connected_users(self) -> List[str]:
        """Retorna lista de usuarios conectados."""
        return list(self.active_connections.keys())

    def get_connection_count(self) -> int:
        """Retorna el numero total de conexiones."""
        return sum(len(conns) for conns in self.active_connections.values())

    def is_user_connected(self, user_id: str) -> bool:
        """Verifica si un usuario tiene conexiones activas."""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0


# Instancia global del manager
manager = ConnectionManager()


# Funciones helper para enviar notificaciones desde cualquier parte
async def notify_user(
    user_id: str,
    notification_type: NotificationType,
    title: str,
    message: str,
    priority: NotificationPriority = NotificationPriority.MEDIUM,
    data: Optional[Dict] = None
) -> int:
    """Envia una notificacion a un usuario especifico."""
    msg = WebSocketMessage(
        type="notification",
        notification_type=notification_type,
        title=title,
        message=message,
        priority=priority,
        data=data
    )
    return await manager.send_personal_message(msg, user_id)


async def notify_admins(
    notification_type: NotificationType,
    title: str,
    message: str,
    priority: NotificationPriority = NotificationPriority.MEDIUM,
    data: Optional[Dict] = None
) -> int:
    """Envia una notificacion a todos los administradores."""
    msg = WebSocketMessage(
        type="notification",
        notification_type=notification_type,
        title=title,
        message=message,
        priority=priority,
        data=data
    )
    return await manager.send_to_admins(msg)


async def notify_all(
    notification_type: NotificationType,
    title: str,
    message: str,
    priority: NotificationPriority = NotificationPriority.MEDIUM,
    data: Optional[Dict] = None
) -> int:
    """Envia una notificacion a todos los usuarios conectados."""
    msg = WebSocketMessage(
        type="notification",
        notification_type=notification_type,
        title=title,
        message=message,
        priority=priority,
        data=data
    )
    return await manager.broadcast(msg)


# Notificaciones especificas de auditoria
async def notify_audit_started(
    user_id: str,
    contract_address: str,
    audit_id: str
) -> int:
    """Notifica que una auditoria ha comenzado."""
    return await notify_user(
        user_id=user_id,
        notification_type=NotificationType.AUDIT_STARTED,
        title="Auditoria Iniciada",
        message=f"Se ha iniciado la auditoria del contrato {contract_address[:10]}...",
        priority=NotificationPriority.MEDIUM,
        data={
            "audit_id": audit_id,
            "contract_address": contract_address
        }
    )


async def notify_audit_completed(
    user_id: str,
    contract_address: str,
    audit_id: str,
    risk_level: str,
    findings_count: int
) -> int:
    """Notifica que una auditoria ha finalizado."""
    priority = NotificationPriority.HIGH if risk_level in ["HIGH", "CRITICAL"] else NotificationPriority.MEDIUM

    return await notify_user(
        user_id=user_id,
        notification_type=NotificationType.AUDIT_COMPLETED,
        title="Auditoria Completada",
        message=f"Auditoria finalizada. Riesgo: {risk_level}. {findings_count} hallazgos encontrados.",
        priority=priority,
        data={
            "audit_id": audit_id,
            "contract_address": contract_address,
            "risk_level": risk_level,
            "findings_count": findings_count
        }
    )


async def notify_audit_finding(
    user_id: str,
    audit_id: str,
    finding_type: str,
    severity: str,
    description: str
) -> int:
    """Notifica un hallazgo de auditoria critico."""
    if severity not in ["HIGH", "CRITICAL"]:
        return 0  # Solo notificar hallazgos importantes

    return await notify_user(
        user_id=user_id,
        notification_type=NotificationType.AUDIT_FINDING,
        title=f"Hallazgo {severity}",
        message=description[:100] + "..." if len(description) > 100 else description,
        priority=NotificationPriority.HIGH if severity == "HIGH" else NotificationPriority.CRITICAL,
        data={
            "audit_id": audit_id,
            "finding_type": finding_type,
            "severity": severity
        }
    )


async def notify_compliance_alert(
    user_id: str,
    alert_type: str,
    entity_type: str,
    entity_id: str,
    message: str
) -> int:
    """Notifica una alerta de compliance."""
    return await notify_user(
        user_id=user_id,
        notification_type=NotificationType.COMPLIANCE_ALERT,
        title=f"Alerta de Compliance: {alert_type}",
        message=message,
        priority=NotificationPriority.HIGH,
        data={
            "alert_type": alert_type,
            "entity_type": entity_type,
            "entity_id": entity_id
        }
    )
