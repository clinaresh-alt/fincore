"""
Webhook Service para FinCore.

Envía notificaciones en tiempo real a:
- Frontend via WebSocket/SSE
- Servicios externos (integraciones)
- Sistemas de monitoreo

Eventos soportados:
- remittance.created
- remittance.locked
- remittance.released
- remittance.refunded
- remittance.expired
- blockchain.transaction.confirmed
- blockchain.transaction.failed
- alert.discrepancy
- alert.low_balance

Uso:
    from app.services.webhook_service import WebhookService, webhook_service

    # Enviar webhook
    await webhook_service.send(
        event="remittance.locked",
        data={"remittance_id": "...", "amount": 1000},
    )

    # Registrar endpoint externo
    webhook_service.register_endpoint(
        url="https://api.partner.com/webhooks",
        secret="shared_secret",
        events=["remittance.*"],
    )
"""
import os
import json
import hmac
import hashlib
import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4
import fnmatch

from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base, SessionLocal

# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

# Redis para PubSub
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


# ==================== Configuración ====================

WEBHOOK_TIMEOUT = int(os.getenv("WEBHOOK_TIMEOUT", "10"))  # segundos
WEBHOOK_MAX_RETRIES = int(os.getenv("WEBHOOK_MAX_RETRIES", "3"))
WEBHOOK_RETRY_DELAY = int(os.getenv("WEBHOOK_RETRY_DELAY", "5"))  # segundos

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
WEBHOOK_CHANNEL = "fincore:webhooks"

# Secret para firmar webhooks
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "fincore-webhook-secret-change-me")


# ==================== Métricas Prometheus ====================

WEBHOOKS_SENT = Counter(
    'webhooks_sent_total',
    'Total de webhooks enviados',
    ['event_type', 'status']
)

WEBHOOK_LATENCY = Histogram(
    'webhook_latency_seconds',
    'Latencia de envío de webhooks',
    ['endpoint'],
    buckets=[0.1, 0.25, 0.5, 1, 2.5, 5, 10]
)

WEBHOOK_QUEUE_SIZE = Gauge(
    'webhook_queue_size',
    'Tamaño de la cola de webhooks pendientes'
)

ACTIVE_CONNECTIONS = Gauge(
    'websocket_active_connections',
    'Conexiones WebSocket activas',
    ['channel']
)


# ==================== Tipos ====================

class WebhookEvent(str, Enum):
    """Tipos de eventos de webhook."""
    # Remesas
    REMITTANCE_CREATED = "remittance.created"
    REMITTANCE_DEPOSITED = "remittance.deposited"
    REMITTANCE_LOCKED = "remittance.locked"
    REMITTANCE_PROCESSING = "remittance.processing"
    REMITTANCE_DISBURSED = "remittance.disbursed"
    REMITTANCE_COMPLETED = "remittance.completed"
    REMITTANCE_REFUNDED = "remittance.refunded"
    REMITTANCE_FAILED = "remittance.failed"
    REMITTANCE_EXPIRED = "remittance.expired"

    # Blockchain
    TX_SUBMITTED = "blockchain.tx.submitted"
    TX_MINED = "blockchain.tx.mined"
    TX_CONFIRMED = "blockchain.tx.confirmed"
    TX_FAILED = "blockchain.tx.failed"
    TX_REPLACED = "blockchain.tx.replaced"

    # Alertas
    ALERT_DISCREPANCY = "alert.discrepancy"
    ALERT_LOW_BALANCE = "alert.low_balance"
    ALERT_HIGH_GAS = "alert.high_gas"
    ALERT_CONTRACT_PAUSED = "alert.contract_paused"

    # Sistema
    SYSTEM_MAINTENANCE = "system.maintenance"
    SYSTEM_DEGRADED = "system.degraded"


@dataclass
class WebhookPayload:
    """Payload de un webhook."""
    id: str
    event: str
    timestamp: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "event": self.event,
            "timestamp": self.timestamp,
            "data": self.data,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass
class WebhookEndpoint:
    """Configuración de un endpoint de webhook."""
    id: str
    url: str
    secret: str
    events: List[str]  # Patrones con wildcard: ["remittance.*", "alert.*"]
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    failure_count: int = 0
    headers: Dict[str, str] = field(default_factory=dict)

    def matches_event(self, event: str) -> bool:
        """Verifica si el endpoint debe recibir este evento."""
        for pattern in self.events:
            if fnmatch.fnmatch(event, pattern):
                return True
        return False


@dataclass
class WebhookDelivery:
    """Registro de un intento de entrega."""
    id: str
    webhook_id: str
    endpoint_id: str
    event: str
    payload: Dict
    status: str  # pending, success, failed
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    attempts: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    delivered_at: Optional[datetime] = None
    error: Optional[str] = None


# ==================== Excepciones ====================

class WebhookError(Exception):
    """Error base de webhooks."""
    pass


class DeliveryError(WebhookError):
    """Error de entrega de webhook."""
    pass


class SignatureError(WebhookError):
    """Error de firma de webhook."""
    pass


# ==================== Modelo de DB ====================

class WebhookEndpointModel(Base):
    """Modelo de endpoint de webhook en DB."""
    __tablename__ = "webhook_endpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    url = Column(String(500), nullable=False)
    secret = Column(String(255), nullable=False)
    events = Column(JSONB, default=[])  # Lista de patrones
    enabled = Column(Boolean, default=True)
    headers = Column(JSONB, default={})

    # Estadísticas
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_success = Column(DateTime(timezone=True), nullable=True)
    last_failure = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    name = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class WebhookDeliveryModel(Base):
    """Registro de entregas de webhooks."""
    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    endpoint_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    event = Column(String(100), nullable=False, index=True)
    payload = Column(JSONB, nullable=False)

    # Estado
    status = Column(String(20), default="pending")  # pending, success, failed
    attempts = Column(Integer, default=0)

    # Respuesta
    response_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    delivered_at = Column(DateTime(timezone=True), nullable=True)


# ==================== Servicio Principal ====================

class WebhookService:
    """
    Servicio de webhooks para notificaciones en tiempo real.

    Features:
    - Entrega a endpoints HTTP externos
    - PubSub via Redis para WebSockets internos
    - Firma HMAC-SHA256 para verificación
    - Reintentos automáticos con backoff
    - Registro de entregas para debugging
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._endpoints: Dict[str, WebhookEndpoint] = {}
        self._local_subscribers: Dict[str, List[Callable]] = {}
        self._redis: Optional[Any] = None
        self._running = False
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

        # Inicializar Redis si está disponible
        self._init_redis()

        # Cargar endpoints de DB
        self._load_endpoints()

    def _init_redis(self):
        """Inicializa conexión Redis para PubSub."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis no disponible, PubSub deshabilitado")
            return

        try:
            self._redis = redis.from_url(REDIS_URL)
            self._redis.ping()
            logger.info("Redis conectado para webhooks")
        except Exception as e:
            logger.warning(f"No se pudo conectar a Redis: {e}")
            self._redis = None

    def _load_endpoints(self):
        """Carga endpoints de la base de datos."""
        try:
            db = self.db
            endpoints = db.query(WebhookEndpointModel).filter(
                WebhookEndpointModel.enabled == True
            ).all()

            for ep in endpoints:
                self._endpoints[str(ep.id)] = WebhookEndpoint(
                    id=str(ep.id),
                    url=ep.url,
                    secret=ep.secret,
                    events=ep.events or [],
                    enabled=ep.enabled,
                    headers=ep.headers or {},
                    failure_count=ep.failure_count,
                    last_success=ep.last_success,
                    last_failure=ep.last_failure,
                )

            logger.info(f"Cargados {len(self._endpoints)} endpoints de webhook")

        except Exception as e:
            logger.error(f"Error cargando endpoints: {e}")

    @property
    def db(self) -> Session:
        """Obtiene sesión de DB."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    # ==================== API Pública ====================

    async def send(
        self,
        event: str,
        data: Dict[str, Any],
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Envía un webhook a todos los endpoints suscritos.

        Args:
            event: Tipo de evento (ej: "remittance.locked")
            data: Datos del evento
            metadata: Metadata adicional

        Returns:
            ID del webhook
        """
        webhook_id = str(uuid4())

        payload = WebhookPayload(
            id=webhook_id,
            event=event,
            timestamp=datetime.utcnow().isoformat(),
            data=data,
            metadata=metadata or {},
        )

        # Publicar en Redis para subscribers internos (WebSockets)
        await self._publish_redis(payload)

        # Notificar subscribers locales
        await self._notify_local(event, payload)

        # Encolar para entrega HTTP
        await self._queue.put((payload, event))
        WEBHOOK_QUEUE_SIZE.set(self._queue.qsize())

        logger.info(f"Webhook encolado: {event} (ID: {webhook_id})")
        return webhook_id

    async def send_to_endpoint(
        self,
        endpoint_id: str,
        event: str,
        data: Dict[str, Any],
    ) -> bool:
        """Envía un webhook a un endpoint específico."""
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            raise WebhookError(f"Endpoint no encontrado: {endpoint_id}")

        payload = WebhookPayload(
            id=str(uuid4()),
            event=event,
            timestamp=datetime.utcnow().isoformat(),
            data=data,
        )

        return await self._deliver(endpoint, payload)

    def subscribe(
        self,
        event_pattern: str,
        callback: Callable[[WebhookPayload], None],
    ):
        """
        Suscribe un callback local a un patrón de eventos.

        Args:
            event_pattern: Patrón con wildcard (ej: "remittance.*")
            callback: Función a llamar
        """
        if event_pattern not in self._local_subscribers:
            self._local_subscribers[event_pattern] = []
        self._local_subscribers[event_pattern].append(callback)

    def register_endpoint(
        self,
        url: str,
        secret: str,
        events: List[str],
        name: Optional[str] = None,
        headers: Optional[Dict] = None,
    ) -> str:
        """
        Registra un nuevo endpoint de webhook.

        Args:
            url: URL del endpoint
            secret: Secret compartido para firma
            events: Lista de patrones de eventos
            name: Nombre descriptivo
            headers: Headers adicionales

        Returns:
            ID del endpoint
        """
        endpoint_id = str(uuid4())

        # Guardar en DB
        db_endpoint = WebhookEndpointModel(
            id=endpoint_id,
            url=url,
            secret=secret,
            events=events,
            name=name,
            headers=headers or {},
        )
        self.db.add(db_endpoint)
        self.db.commit()

        # Agregar a cache
        self._endpoints[endpoint_id] = WebhookEndpoint(
            id=endpoint_id,
            url=url,
            secret=secret,
            events=events,
            headers=headers or {},
        )

        logger.info(f"Endpoint registrado: {url} (ID: {endpoint_id})")
        return endpoint_id

    def unregister_endpoint(self, endpoint_id: str) -> bool:
        """Elimina un endpoint de webhook."""
        if endpoint_id in self._endpoints:
            del self._endpoints[endpoint_id]

        db_endpoint = self.db.query(WebhookEndpointModel).filter(
            WebhookEndpointModel.id == endpoint_id
        ).first()

        if db_endpoint:
            db_endpoint.enabled = False
            self.db.commit()
            return True

        return False

    # ==================== Entrega ====================

    async def _deliver(
        self,
        endpoint: WebhookEndpoint,
        payload: WebhookPayload,
    ) -> bool:
        """Entrega un webhook a un endpoint."""
        if not endpoint.enabled:
            return False

        # Generar firma
        signature = self._sign_payload(payload.to_json(), endpoint.secret)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-ID": payload.id,
            "X-Webhook-Event": payload.event,
            "X-Webhook-Timestamp": payload.timestamp,
            "X-Webhook-Signature": f"sha256={signature}",
            **endpoint.headers,
        }

        # Intentar entrega con reintentos
        for attempt in range(WEBHOOK_MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    with WEBHOOK_LATENCY.labels(endpoint=endpoint.url[:50]).time():
                        async with session.post(
                            endpoint.url,
                            json=payload.to_dict(),
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=WEBHOOK_TIMEOUT),
                        ) as response:
                            if response.status < 300:
                                # Éxito
                                self._record_success(endpoint, payload)
                                WEBHOOKS_SENT.labels(
                                    event_type=payload.event,
                                    status="success"
                                ).inc()
                                return True

                            # Error del servidor, reintentar
                            if response.status >= 500:
                                raise DeliveryError(
                                    f"Server error: {response.status}"
                                )

                            # Error del cliente, no reintentar
                            error_body = await response.text()
                            self._record_failure(
                                endpoint, payload,
                                f"HTTP {response.status}: {error_body[:200]}"
                            )
                            return False

            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout entregando a {endpoint.url} (intento {attempt + 1})"
                )
            except Exception as e:
                logger.error(
                    f"Error entregando a {endpoint.url}: {e} (intento {attempt + 1})"
                )

            # Esperar antes de reintentar
            if attempt < WEBHOOK_MAX_RETRIES - 1:
                await asyncio.sleep(WEBHOOK_RETRY_DELAY * (attempt + 1))

        # Todos los reintentos fallaron
        self._record_failure(endpoint, payload, "Max retries exceeded")
        WEBHOOKS_SENT.labels(event_type=payload.event, status="failed").inc()
        return False

    def _sign_payload(self, payload: str, secret: str) -> str:
        """Firma el payload con HMAC-SHA256."""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

    def _record_success(self, endpoint: WebhookEndpoint, payload: WebhookPayload):
        """Registra entrega exitosa."""
        endpoint.last_success = datetime.utcnow()
        endpoint.failure_count = 0

        # Actualizar DB
        db_endpoint = self.db.query(WebhookEndpointModel).filter(
            WebhookEndpointModel.id == endpoint.id
        ).first()
        if db_endpoint:
            db_endpoint.last_success = endpoint.last_success
            db_endpoint.success_count += 1
            db_endpoint.failure_count = 0
            self.db.commit()

        # Registrar entrega
        delivery = WebhookDeliveryModel(
            endpoint_id=endpoint.id,
            event=payload.event,
            payload=payload.to_dict(),
            status="success",
            delivered_at=datetime.utcnow(),
        )
        self.db.add(delivery)
        self.db.commit()

    def _record_failure(
        self,
        endpoint: WebhookEndpoint,
        payload: WebhookPayload,
        error: str,
    ):
        """Registra fallo de entrega."""
        endpoint.last_failure = datetime.utcnow()
        endpoint.failure_count += 1

        # Deshabilitar si muchos fallos consecutivos
        if endpoint.failure_count >= 10:
            endpoint.enabled = False
            logger.warning(f"Endpoint deshabilitado por muchos fallos: {endpoint.url}")

        # Actualizar DB
        db_endpoint = self.db.query(WebhookEndpointModel).filter(
            WebhookEndpointModel.id == endpoint.id
        ).first()
        if db_endpoint:
            db_endpoint.last_failure = endpoint.last_failure
            db_endpoint.failure_count = endpoint.failure_count
            db_endpoint.enabled = endpoint.enabled
            self.db.commit()

        # Registrar entrega fallida
        delivery = WebhookDeliveryModel(
            endpoint_id=endpoint.id,
            event=payload.event,
            payload=payload.to_dict(),
            status="failed",
            error=error,
        )
        self.db.add(delivery)
        self.db.commit()

    # ==================== PubSub ====================

    async def _publish_redis(self, payload: WebhookPayload):
        """Publica evento en Redis para WebSockets."""
        if not self._redis:
            return

        try:
            message = {
                "channel": payload.event.split(".")[0],  # Ej: "remittance"
                "payload": payload.to_dict(),
            }
            self._redis.publish(WEBHOOK_CHANNEL, json.dumps(message, default=str))
        except Exception as e:
            logger.error(f"Error publicando en Redis: {e}")

    async def _notify_local(self, event: str, payload: WebhookPayload):
        """Notifica subscribers locales."""
        for pattern, callbacks in self._local_subscribers.items():
            if fnmatch.fnmatch(event, pattern):
                for callback in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(payload)
                        else:
                            callback(payload)
                    except Exception as e:
                        logger.error(f"Error en callback local: {e}")

    # ==================== Worker ====================

    async def start(self):
        """Inicia el worker de entrega."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Webhook worker iniciado")

    async def stop(self):
        """Detiene el worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Webhook worker detenido")

    async def _worker(self):
        """Worker que procesa la cola de webhooks."""
        while self._running:
            try:
                payload, event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                WEBHOOK_QUEUE_SIZE.set(self._queue.qsize())

                # Encontrar endpoints que coincidan
                matching_endpoints = [
                    ep for ep in self._endpoints.values()
                    if ep.enabled and ep.matches_event(event)
                ]

                # Entregar en paralelo
                if matching_endpoints:
                    tasks = [
                        self._deliver(ep, payload)
                        for ep in matching_endpoints
                    ]
                    await asyncio.gather(*tasks, return_exceptions=True)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error en worker: {e}")

    # ==================== Verificación de firma ====================

    @staticmethod
    def verify_signature(
        payload: str,
        signature: str,
        secret: str,
    ) -> bool:
        """
        Verifica la firma de un webhook entrante.

        Args:
            payload: Body del request como string
            signature: Header X-Webhook-Signature
            secret: Secret compartido

        Returns:
            True si la firma es válida
        """
        if not signature.startswith("sha256="):
            return False

        expected = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        actual = signature[7:]  # Remover "sha256="
        return hmac.compare_digest(expected, actual)

    # ==================== Utilidades ====================

    def get_endpoints(self) -> List[Dict]:
        """Obtiene lista de endpoints registrados."""
        return [
            {
                "id": ep.id,
                "url": ep.url,
                "events": ep.events,
                "enabled": ep.enabled,
                "failure_count": ep.failure_count,
                "last_success": ep.last_success.isoformat() if ep.last_success else None,
                "last_failure": ep.last_failure.isoformat() if ep.last_failure else None,
            }
            for ep in self._endpoints.values()
        ]

    def get_recent_deliveries(
        self,
        limit: int = 100,
        event: Optional[str] = None,
    ) -> List[Dict]:
        """Obtiene entregas recientes."""
        query = self.db.query(WebhookDeliveryModel).order_by(
            WebhookDeliveryModel.created_at.desc()
        )

        if event:
            query = query.filter(WebhookDeliveryModel.event == event)

        deliveries = query.limit(limit).all()

        return [
            {
                "id": str(d.id),
                "endpoint_id": str(d.endpoint_id),
                "event": d.event,
                "status": d.status,
                "response_code": d.response_code,
                "created_at": d.created_at.isoformat(),
                "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
            }
            for d in deliveries
        ]

    def close(self):
        """Cierra conexiones."""
        if self._db:
            self._db.close()
        if self._redis:
            self._redis.close()


# ==================== Singleton ====================

_webhook_service: Optional[WebhookService] = None


def get_webhook_service() -> WebhookService:
    """Obtiene la instancia singleton del servicio."""
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookService()
    return _webhook_service


# Alias para compatibilidad
webhook_service = get_webhook_service
