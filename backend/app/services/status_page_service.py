"""
Servicio de Status Page para FinCore.

Implementa una pagina de estado compatible con Statuspage.io:
- Monitoreo de componentes del sistema
- Gestion de incidentes
- Notificaciones a suscriptores
- API publica de estado
- Integracion con sistemas de monitoreo

Uso:
    from app.services.status_page_service import StatusPageService, status_page

    # Obtener estado actual
    status = await status_page.get_status()

    # Crear incidente
    await status_page.create_incident(
        title="Degradacion de servicio",
        impact="minor",
        components=["api"],
    )
"""
import os
import json
import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from app.core.database import Base, SessionLocal

# Prometheus metrics
from prometheus_client import Gauge, Counter, Histogram

logger = logging.getLogger(__name__)


# ==================== Configuracion ====================

# Statuspage.io (opcional - para sync)
STATUSPAGE_API_KEY = os.getenv("STATUSPAGE_API_KEY", "")
STATUSPAGE_PAGE_ID = os.getenv("STATUSPAGE_PAGE_ID", "")

# Notificaciones
STATUS_WEBHOOK_URL = os.getenv("STATUS_WEBHOOK_URL", "")
STATUS_EMAIL_ENABLED = os.getenv("STATUS_EMAIL_ENABLED", "false").lower() == "true"

# Health check
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))  # segundos


# ==================== Metricas Prometheus ====================

SYSTEM_STATUS_GAUGE = Gauge(
    'status_page_system_status',
    'Estado general del sistema (1=operational, 0=down)',
)

COMPONENT_STATUS = Gauge(
    'status_page_component_status',
    'Estado de cada componente',
    ['component']
)

ACTIVE_INCIDENTS = Gauge(
    'status_page_active_incidents',
    'Numero de incidentes activos',
    ['impact']
)

INCIDENT_DURATION = Histogram(
    'status_page_incident_duration_seconds',
    'Duracion de incidentes en segundos',
    ['impact'],
    buckets=[300, 900, 1800, 3600, 7200, 14400, 28800, 86400]
)

UPTIME_PERCENTAGE = Gauge(
    'status_page_uptime_percentage',
    'Porcentaje de uptime',
    ['component', 'period']
)


# ==================== Tipos ====================

class ComponentStatus(str, Enum):
    """Estados posibles de un componente."""
    OPERATIONAL = "operational"
    DEGRADED_PERFORMANCE = "degraded_performance"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    UNDER_MAINTENANCE = "under_maintenance"


class IncidentImpact(str, Enum):
    """Impacto del incidente."""
    NONE = "none"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    """Estado del incidente."""
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    POSTMORTEM = "postmortem"


class MaintenanceStatus(str, Enum):
    """Estado de mantenimiento."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Component:
    """Componente del sistema."""
    id: str
    name: str
    description: str
    status: ComponentStatus
    group: Optional[str] = None
    position: int = 0
    showcase: bool = True
    only_show_if_degraded: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "group": self.group,
            "position": self.position,
            "showcase": self.showcase,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class IncidentUpdate:
    """Actualizacion de incidente."""
    id: str
    incident_id: str
    status: IncidentStatus
    body: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_by: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "status": self.status.value,
            "body": self.body,
            "created_at": self.created_at.isoformat(),
            "updated_by": self.updated_by,
        }


@dataclass
class Incident:
    """Incidente de servicio."""
    id: str
    name: str
    status: IncidentStatus
    impact: IncidentImpact
    shortlink: Optional[str]
    components: List[str]
    component_statuses: Dict[str, ComponentStatus]
    updates: List[IncidentUpdate] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    monitoring_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "impact": self.impact.value,
            "shortlink": self.shortlink,
            "components": self.components,
            "component_statuses": {k: v.value for k, v in self.component_statuses.items()},
            "updates": [u.to_dict() for u in self.updates],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class ScheduledMaintenance:
    """Mantenimiento programado."""
    id: str
    name: str
    status: MaintenanceStatus
    impact: IncidentImpact
    components: List[str]
    scheduled_for: datetime
    scheduled_until: datetime
    description: str
    updates: List[Dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "impact": self.impact.value,
            "components": self.components,
            "scheduled_for": self.scheduled_for.isoformat(),
            "scheduled_until": self.scheduled_until.isoformat(),
            "description": self.description,
            "updates": self.updates,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SystemStatus:
    """Estado general del sistema."""
    indicator: str  # none, minor, major, critical
    description: str
    components: List[Component]
    incidents: List[Incident]
    scheduled_maintenances: List[ScheduledMaintenance]
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        return {
            "status": {
                "indicator": self.indicator,
                "description": self.description,
            },
            "components": [c.to_dict() for c in self.components],
            "incidents": [i.to_dict() for i in self.incidents],
            "scheduled_maintenances": [m.to_dict() for m in self.scheduled_maintenances],
            "page": {
                "id": "fincore",
                "name": "FinCore",
                "url": "https://status.fincore.com",
                "updated_at": self.updated_at.isoformat(),
            }
        }


# ==================== Modelos de DB ====================

class ComponentModel(Base):
    """Componentes en DB."""
    __tablename__ = "status_components"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    status = Column(String(30), default="operational")
    group_name = Column(String(100), nullable=True)
    position = Column(Integer, default=0)
    showcase = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class IncidentModel(Base):
    """Incidentes en DB."""
    __tablename__ = "status_incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    status = Column(String(30), nullable=False)
    impact = Column(String(20), nullable=False)
    shortlink = Column(String(100), nullable=True)
    components = Column(JSONB, default=[])
    component_statuses = Column(JSONB, default={})

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    monitoring_at = Column(DateTime(timezone=True), nullable=True)


class IncidentUpdateModel(Base):
    """Actualizaciones de incidentes."""
    __tablename__ = "status_incident_updates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    incident_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    status = Column(String(30), nullable=False)
    body = Column(Text, nullable=False)
    updated_by = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class MaintenanceModel(Base):
    """Mantenimientos programados."""
    __tablename__ = "status_maintenances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    status = Column(String(30), nullable=False)
    impact = Column(String(20), nullable=False)
    components = Column(JSONB, default=[])
    description = Column(Text, nullable=True)

    scheduled_for = Column(DateTime(timezone=True), nullable=False)
    scheduled_until = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class SubscriberModel(Base):
    """Suscriptores a notificaciones."""
    __tablename__ = "status_subscribers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), nullable=False, unique=True)
    components = Column(JSONB, default=[])  # Lista de component_ids
    verified = Column(Boolean, default=False)
    verification_token = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    unsubscribed_at = Column(DateTime(timezone=True), nullable=True)


class UptimeRecordModel(Base):
    """Registros de uptime."""
    __tablename__ = "status_uptime_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    component_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    status = Column(String(30), nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    recorded_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)


# ==================== Servicio Principal ====================

class StatusPageService:
    """
    Servicio de Status Page.

    Features:
    - Monitoreo de componentes
    - Gestion de incidentes
    - Mantenimientos programados
    - Notificaciones a suscriptores
    - API compatible con Statuspage.io
    - Calculo de uptime
    """

    # Componentes por defecto
    DEFAULT_COMPONENTS = [
        ("api", "API", "REST API principal", "Core"),
        ("web_app", "Web Application", "Aplicacion web", "Core"),
        ("blockchain", "Blockchain Services", "Servicios blockchain", "Infrastructure"),
        ("database", "Database", "Base de datos", "Infrastructure"),
        ("webhooks", "Webhooks", "Sistema de webhooks", "Integrations"),
        ("bank_integration", "Bank Integration", "Integracion bancaria", "Integrations"),
    ]

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._components: Dict[str, Component] = {}
        self._incidents: Dict[str, Incident] = {}
        self._maintenances: Dict[str, ScheduledMaintenance] = {}
        self._subscribers: List[str] = []
        self._health_callbacks: Dict[str, Callable] = {}
        self._running = False
        self._health_task: Optional[asyncio.Task] = None

        # Inicializar componentes
        self._initialize_components()

    def _initialize_components(self):
        """Inicializa componentes por defecto."""
        try:
            # Cargar de DB o crear defaults
            db_components = self.db.query(ComponentModel).all()

            if db_components:
                for c in db_components:
                    self._components[c.name] = Component(
                        id=str(c.id),
                        name=c.name,
                        description=c.description or "",
                        status=ComponentStatus(c.status),
                        group=c.group_name,
                        position=c.position,
                        showcase=c.showcase,
                        created_at=c.created_at,
                        updated_at=c.updated_at,
                    )
            else:
                # Crear defaults
                for i, (name, display, desc, group) in enumerate(self.DEFAULT_COMPONENTS):
                    component = ComponentModel(
                        name=name,
                        description=desc,
                        status="operational",
                        group_name=group,
                        position=i,
                    )
                    self.db.add(component)

                    self._components[name] = Component(
                        id=str(component.id),
                        name=name,
                        description=desc,
                        status=ComponentStatus.OPERATIONAL,
                        group=group,
                        position=i,
                    )

                self.db.commit()

            # Cargar incidentes activos
            active_incidents = self.db.query(IncidentModel).filter(
                IncidentModel.status != "resolved"
            ).all()

            for inc in active_incidents:
                updates = self.db.query(IncidentUpdateModel).filter(
                    IncidentUpdateModel.incident_id == inc.id
                ).order_by(IncidentUpdateModel.created_at.desc()).all()

                self._incidents[str(inc.id)] = Incident(
                    id=str(inc.id),
                    name=inc.name,
                    status=IncidentStatus(inc.status),
                    impact=IncidentImpact(inc.impact),
                    shortlink=inc.shortlink,
                    components=inc.components or [],
                    component_statuses={k: ComponentStatus(v) for k, v in (inc.component_statuses or {}).items()},
                    updates=[
                        IncidentUpdate(
                            id=str(u.id),
                            incident_id=str(u.incident_id),
                            status=IncidentStatus(u.status),
                            body=u.body,
                            created_at=u.created_at,
                            updated_by=u.updated_by,
                        )
                        for u in updates
                    ],
                    created_at=inc.created_at,
                    updated_at=inc.updated_at,
                    resolved_at=inc.resolved_at,
                )

            # Actualizar metricas
            self._update_metrics()

            logger.info(f"StatusPageService inicializado: {len(self._components)} componentes")

        except Exception as e:
            logger.error(f"Error inicializando StatusPageService: {e}")

    @property
    def db(self) -> Session:
        """Obtiene sesion de DB."""
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    # ==================== Estado del Sistema ====================

    async def get_status(self) -> SystemStatus:
        """Obtiene el estado actual del sistema."""
        # Calcular indicador general
        indicator = self._calculate_indicator()

        # Descripcion basada en indicador
        descriptions = {
            "none": "All Systems Operational",
            "minor": "Minor Service Degradation",
            "major": "Partial System Outage",
            "critical": "Major System Outage",
            "maintenance": "Scheduled Maintenance in Progress",
        }

        # Obtener mantenimientos activos
        maintenances = self._get_active_maintenances()

        return SystemStatus(
            indicator=indicator,
            description=descriptions.get(indicator, "Unknown"),
            components=list(self._components.values()),
            incidents=list(self._incidents.values()),
            scheduled_maintenances=maintenances,
        )

    def _calculate_indicator(self) -> str:
        """Calcula el indicador general del sistema."""
        # Verificar incidentes activos
        for incident in self._incidents.values():
            if incident.status != IncidentStatus.RESOLVED:
                if incident.impact == IncidentImpact.CRITICAL:
                    return "critical"
                elif incident.impact == IncidentImpact.MAJOR:
                    return "major"
                elif incident.impact == IncidentImpact.MINOR:
                    return "minor"

        # Verificar componentes
        for component in self._components.values():
            if component.status == ComponentStatus.MAJOR_OUTAGE:
                return "critical"
            elif component.status == ComponentStatus.PARTIAL_OUTAGE:
                return "major"
            elif component.status in (ComponentStatus.DEGRADED_PERFORMANCE, ComponentStatus.UNDER_MAINTENANCE):
                return "minor"

        return "none"

    def _get_active_maintenances(self) -> List[ScheduledMaintenance]:
        """Obtiene mantenimientos activos."""
        now = datetime.utcnow()
        return [
            m for m in self._maintenances.values()
            if m.status in (MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS)
            and m.scheduled_until > now
        ]

    # ==================== Gestion de Componentes ====================

    async def update_component_status(
        self,
        component_name: str,
        status: ComponentStatus,
        notify: bool = True,
    ) -> Optional[Component]:
        """Actualiza el estado de un componente."""
        if component_name not in self._components:
            logger.warning(f"Componente no encontrado: {component_name}")
            return None

        component = self._components[component_name]
        old_status = component.status

        if old_status == status:
            return component

        # Actualizar
        component.status = status
        component.updated_at = datetime.utcnow()

        # Actualizar en DB
        db_component = self.db.query(ComponentModel).filter(
            ComponentModel.name == component_name
        ).first()

        if db_component:
            db_component.status = status.value
            db_component.updated_at = component.updated_at
            self.db.commit()

        # Metrica
        status_value = {
            ComponentStatus.OPERATIONAL: 1.0,
            ComponentStatus.DEGRADED_PERFORMANCE: 0.75,
            ComponentStatus.PARTIAL_OUTAGE: 0.5,
            ComponentStatus.MAJOR_OUTAGE: 0.0,
            ComponentStatus.UNDER_MAINTENANCE: 0.5,
        }.get(status, 0.5)

        COMPONENT_STATUS.labels(component=component_name).set(status_value)

        # Registrar uptime
        uptime = UptimeRecordModel(
            component_id=component.id,
            status=status.value,
        )
        self.db.add(uptime)
        self.db.commit()

        # Notificar si cambio significativo
        if notify and old_status != status:
            await self._notify_component_change(component, old_status, status)

        logger.info(f"Componente {component_name}: {old_status.value} -> {status.value}")

        self._update_metrics()
        return component

    async def get_component(self, component_name: str) -> Optional[Component]:
        """Obtiene un componente."""
        return self._components.get(component_name)

    def get_all_components(self) -> List[Component]:
        """Obtiene todos los componentes."""
        return list(self._components.values())

    # ==================== Gestion de Incidentes ====================

    async def create_incident(
        self,
        name: str,
        impact: IncidentImpact,
        components: List[str],
        message: str,
        status: IncidentStatus = IncidentStatus.INVESTIGATING,
        notify: bool = True,
        created_by: Optional[str] = None,
    ) -> Incident:
        """Crea un nuevo incidente."""
        incident_id = str(uuid4())
        now = datetime.utcnow()

        # Determinar estado de componentes afectados
        component_statuses = {}
        for comp_name in components:
            if impact == IncidentImpact.CRITICAL:
                component_statuses[comp_name] = ComponentStatus.MAJOR_OUTAGE
            elif impact == IncidentImpact.MAJOR:
                component_statuses[comp_name] = ComponentStatus.PARTIAL_OUTAGE
            else:
                component_statuses[comp_name] = ComponentStatus.DEGRADED_PERFORMANCE

        # Crear update inicial
        initial_update = IncidentUpdate(
            id=str(uuid4()),
            incident_id=incident_id,
            status=status,
            body=message,
            created_at=now,
            updated_by=created_by,
        )

        incident = Incident(
            id=incident_id,
            name=name,
            status=status,
            impact=impact,
            shortlink=f"https://status.fincore.com/incidents/{incident_id[:8]}",
            components=components,
            component_statuses=component_statuses,
            updates=[initial_update],
            created_at=now,
            updated_at=now,
        )

        # Guardar en DB
        db_incident = IncidentModel(
            id=incident_id,
            name=name,
            status=status.value,
            impact=impact.value,
            shortlink=incident.shortlink,
            components=components,
            component_statuses={k: v.value for k, v in component_statuses.items()},
        )
        self.db.add(db_incident)

        db_update = IncidentUpdateModel(
            id=initial_update.id,
            incident_id=incident_id,
            status=status.value,
            body=message,
            updated_by=created_by,
        )
        self.db.add(db_update)

        self.db.commit()

        # Actualizar componentes afectados
        for comp_name, comp_status in component_statuses.items():
            await self.update_component_status(comp_name, comp_status, notify=False)

        # Guardar en memoria
        self._incidents[incident_id] = incident

        # Notificar
        if notify:
            await self._notify_incident_created(incident)

        # Metricas
        ACTIVE_INCIDENTS.labels(impact=impact.value).inc()

        logger.warning(f"Incidente creado: {name} (impact={impact.value})")

        self._update_metrics()
        return incident

    async def update_incident(
        self,
        incident_id: str,
        status: IncidentStatus,
        message: str,
        updated_by: Optional[str] = None,
        notify: bool = True,
    ) -> Optional[Incident]:
        """Actualiza un incidente existente."""
        if incident_id not in self._incidents:
            logger.warning(f"Incidente no encontrado: {incident_id}")
            return None

        incident = self._incidents[incident_id]
        old_status = incident.status
        now = datetime.utcnow()

        # Crear update
        update = IncidentUpdate(
            id=str(uuid4()),
            incident_id=incident_id,
            status=status,
            body=message,
            created_at=now,
            updated_by=updated_by,
        )

        # Actualizar incidente
        incident.status = status
        incident.updated_at = now
        incident.updates.insert(0, update)

        if status == IncidentStatus.MONITORING and not incident.monitoring_at:
            incident.monitoring_at = now
        elif status == IncidentStatus.RESOLVED:
            incident.resolved_at = now

            # Restaurar componentes
            for comp_name in incident.components:
                await self.update_component_status(
                    comp_name,
                    ComponentStatus.OPERATIONAL,
                    notify=False
                )

            # Registrar duracion
            duration = (now - incident.created_at).total_seconds()
            INCIDENT_DURATION.labels(impact=incident.impact.value).observe(duration)
            ACTIVE_INCIDENTS.labels(impact=incident.impact.value).dec()

        # Actualizar DB
        db_incident = self.db.query(IncidentModel).filter(
            IncidentModel.id == incident_id
        ).first()

        if db_incident:
            db_incident.status = status.value
            db_incident.updated_at = now
            db_incident.resolved_at = incident.resolved_at
            db_incident.monitoring_at = incident.monitoring_at

        db_update = IncidentUpdateModel(
            id=update.id,
            incident_id=incident_id,
            status=status.value,
            body=message,
            updated_by=updated_by,
        )
        self.db.add(db_update)
        self.db.commit()

        # Notificar
        if notify:
            await self._notify_incident_updated(incident, update)

        logger.info(f"Incidente {incident_id}: {old_status.value} -> {status.value}")

        self._update_metrics()
        return incident

    async def resolve_incident(
        self,
        incident_id: str,
        message: str = "This incident has been resolved.",
        resolved_by: Optional[str] = None,
    ) -> Optional[Incident]:
        """Resuelve un incidente."""
        return await self.update_incident(
            incident_id=incident_id,
            status=IncidentStatus.RESOLVED,
            message=message,
            updated_by=resolved_by,
        )

    def get_active_incidents(self) -> List[Incident]:
        """Obtiene incidentes activos."""
        return [
            i for i in self._incidents.values()
            if i.status != IncidentStatus.RESOLVED
        ]

    def get_recent_incidents(self, limit: int = 10) -> List[Incident]:
        """Obtiene incidentes recientes."""
        incidents = list(self._incidents.values())
        incidents.sort(key=lambda x: x.created_at, reverse=True)
        return incidents[:limit]

    # ==================== Mantenimientos ====================

    async def schedule_maintenance(
        self,
        name: str,
        components: List[str],
        scheduled_for: datetime,
        scheduled_until: datetime,
        description: str,
        impact: IncidentImpact = IncidentImpact.MINOR,
        notify: bool = True,
    ) -> ScheduledMaintenance:
        """Programa un mantenimiento."""
        maint_id = str(uuid4())

        maintenance = ScheduledMaintenance(
            id=maint_id,
            name=name,
            status=MaintenanceStatus.SCHEDULED,
            impact=impact,
            components=components,
            scheduled_for=scheduled_for,
            scheduled_until=scheduled_until,
            description=description,
        )

        # Guardar en DB
        db_maint = MaintenanceModel(
            id=maint_id,
            name=name,
            status="scheduled",
            impact=impact.value,
            components=components,
            description=description,
            scheduled_for=scheduled_for,
            scheduled_until=scheduled_until,
        )
        self.db.add(db_maint)
        self.db.commit()

        self._maintenances[maint_id] = maintenance

        if notify:
            await self._notify_maintenance_scheduled(maintenance)

        logger.info(f"Mantenimiento programado: {name} ({scheduled_for} - {scheduled_until})")

        return maintenance

    async def start_maintenance(self, maintenance_id: str) -> Optional[ScheduledMaintenance]:
        """Inicia un mantenimiento programado."""
        if maintenance_id not in self._maintenances:
            return None

        maintenance = self._maintenances[maintenance_id]
        maintenance.status = MaintenanceStatus.IN_PROGRESS

        # Actualizar componentes
        for comp_name in maintenance.components:
            await self.update_component_status(
                comp_name,
                ComponentStatus.UNDER_MAINTENANCE,
                notify=False
            )

        # Actualizar DB
        db_maint = self.db.query(MaintenanceModel).filter(
            MaintenanceModel.id == maintenance_id
        ).first()
        if db_maint:
            db_maint.status = "in_progress"
            self.db.commit()

        return maintenance

    async def complete_maintenance(self, maintenance_id: str) -> Optional[ScheduledMaintenance]:
        """Completa un mantenimiento."""
        if maintenance_id not in self._maintenances:
            return None

        maintenance = self._maintenances[maintenance_id]
        maintenance.status = MaintenanceStatus.COMPLETED

        # Restaurar componentes
        for comp_name in maintenance.components:
            await self.update_component_status(
                comp_name,
                ComponentStatus.OPERATIONAL,
                notify=False
            )

        # Actualizar DB
        db_maint = self.db.query(MaintenanceModel).filter(
            MaintenanceModel.id == maintenance_id
        ).first()
        if db_maint:
            db_maint.status = "completed"
            self.db.commit()

        return maintenance

    # ==================== Suscriptores ====================

    async def subscribe(self, email: str, components: Optional[List[str]] = None) -> str:
        """Suscribe un email a notificaciones."""
        import secrets

        token = secrets.token_urlsafe(32)

        subscriber = SubscriberModel(
            email=email,
            components=components or [],
            verification_token=token,
        )
        self.db.add(subscriber)
        self.db.commit()

        # Enviar email de verificacion
        await self._send_verification_email(email, token)

        return token

    async def verify_subscription(self, token: str) -> bool:
        """Verifica una suscripcion."""
        subscriber = self.db.query(SubscriberModel).filter(
            SubscriberModel.verification_token == token
        ).first()

        if subscriber:
            subscriber.verified = True
            subscriber.verification_token = None
            self.db.commit()
            return True

        return False

    async def unsubscribe(self, email: str) -> bool:
        """Cancela una suscripcion."""
        subscriber = self.db.query(SubscriberModel).filter(
            SubscriberModel.email == email
        ).first()

        if subscriber:
            subscriber.unsubscribed_at = datetime.utcnow()
            self.db.commit()
            return True

        return False

    # ==================== Notificaciones ====================

    async def _notify_incident_created(self, incident: Incident):
        """Notifica creacion de incidente."""
        payload = {
            "type": "incident.created",
            "incident": incident.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self._send_notifications(payload, incident.components)

    async def _notify_incident_updated(self, incident: Incident, update: IncidentUpdate):
        """Notifica actualizacion de incidente."""
        payload = {
            "type": "incident.updated",
            "incident": incident.to_dict(),
            "update": update.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self._send_notifications(payload, incident.components)

    async def _notify_component_change(
        self,
        component: Component,
        old_status: ComponentStatus,
        new_status: ComponentStatus
    ):
        """Notifica cambio de estado de componente."""
        payload = {
            "type": "component.status_change",
            "component": component.to_dict(),
            "previous_status": old_status.value,
            "new_status": new_status.value,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self._send_notifications(payload, [component.name])

    async def _notify_maintenance_scheduled(self, maintenance: ScheduledMaintenance):
        """Notifica mantenimiento programado."""
        payload = {
            "type": "maintenance.scheduled",
            "maintenance": maintenance.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self._send_notifications(payload, maintenance.components)

    async def _send_notifications(self, payload: Dict, components: List[str]):
        """Envia notificaciones a todos los canales."""
        # Webhook
        if STATUS_WEBHOOK_URL:
            try:
                async with aiohttp.ClientSession() as session:
                    await session.post(STATUS_WEBHOOK_URL, json=payload)
            except Exception as e:
                logger.error(f"Error enviando webhook de status: {e}")

        # Statuspage.io sync
        if STATUSPAGE_API_KEY and STATUSPAGE_PAGE_ID:
            await self._sync_to_statuspage(payload)

        # Email a suscriptores
        if STATUS_EMAIL_ENABLED:
            await self._send_subscriber_emails(payload, components)

    async def _sync_to_statuspage(self, payload: Dict):
        """Sincroniza con Statuspage.io."""
        # Implementar integracion con API de Statuspage.io
        pass

    async def _send_subscriber_emails(self, payload: Dict, components: List[str]):
        """Envia emails a suscriptores."""
        # Obtener suscriptores verificados
        subscribers = self.db.query(SubscriberModel).filter(
            SubscriberModel.verified == True,
            SubscriberModel.unsubscribed_at == None,
        ).all()

        for sub in subscribers:
            # Verificar si suscrito a estos componentes
            if not sub.components or any(c in sub.components for c in components):
                # Enviar email (implementar con servicio de email)
                pass

    async def _send_verification_email(self, email: str, token: str):
        """Envia email de verificacion."""
        # Implementar con servicio de email
        logger.info(f"Verificacion pendiente: {email} (token={token[:10]}...)")

    # ==================== Health Checks ====================

    def register_health_check(self, component_name: str, check_fn: Callable):
        """Registra una funcion de health check."""
        self._health_callbacks[component_name] = check_fn

    async def run_health_checks(self):
        """Ejecuta health checks de todos los componentes."""
        for comp_name, check_fn in self._health_callbacks.items():
            try:
                if asyncio.iscoroutinefunction(check_fn):
                    is_healthy = await check_fn()
                else:
                    is_healthy = check_fn()

                new_status = ComponentStatus.OPERATIONAL if is_healthy else ComponentStatus.MAJOR_OUTAGE
                await self.update_component_status(comp_name, new_status)

            except Exception as e:
                logger.error(f"Health check failed for {comp_name}: {e}")
                await self.update_component_status(comp_name, ComponentStatus.MAJOR_OUTAGE)

    async def start_health_monitor(self):
        """Inicia el monitor de health checks."""
        self._running = True

        async def _monitor():
            while self._running:
                await self.run_health_checks()
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)

        self._health_task = asyncio.create_task(_monitor())
        logger.info("Health monitor iniciado")

    async def stop_health_monitor(self):
        """Detiene el monitor de health checks."""
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitor detenido")

    # ==================== Uptime ====================

    async def get_uptime(
        self,
        component_name: str,
        period_days: int = 30,
    ) -> float:
        """Calcula el uptime de un componente."""
        if component_name not in self._components:
            return 0.0

        component = self._components[component_name]
        cutoff = datetime.utcnow() - timedelta(days=period_days)

        records = self.db.query(UptimeRecordModel).filter(
            UptimeRecordModel.component_id == component.id,
            UptimeRecordModel.recorded_at >= cutoff,
        ).order_by(UptimeRecordModel.recorded_at).all()

        if not records:
            return 100.0  # Asumir 100% si no hay registros

        total_time = 0
        operational_time = 0

        for i, record in enumerate(records):
            if i < len(records) - 1:
                duration = (records[i + 1].recorded_at - record.recorded_at).total_seconds()
            else:
                duration = (datetime.utcnow() - record.recorded_at).total_seconds()

            total_time += duration
            if record.status == ComponentStatus.OPERATIONAL.value:
                operational_time += duration

        if total_time == 0:
            return 100.0

        uptime_pct = (operational_time / total_time) * 100
        UPTIME_PERCENTAGE.labels(component=component_name, period=f"{period_days}d").set(uptime_pct)

        return round(uptime_pct, 2)

    async def get_all_uptimes(self, period_days: int = 30) -> Dict[str, float]:
        """Obtiene uptime de todos los componentes."""
        uptimes = {}
        for comp_name in self._components:
            uptimes[comp_name] = await self.get_uptime(comp_name, period_days)
        return uptimes

    # ==================== Metricas ====================

    def _update_metrics(self):
        """Actualiza metricas de Prometheus."""
        indicator = self._calculate_indicator()
        status_value = {
            "none": 1.0,
            "minor": 0.75,
            "major": 0.5,
            "critical": 0.0,
        }.get(indicator, 0.5)

        SYSTEM_STATUS_GAUGE.set(status_value)

    def close(self):
        """Cierra conexiones."""
        if self._db:
            self._db.close()


# ==================== Singleton ====================

_status_page: Optional[StatusPageService] = None


def get_status_page() -> StatusPageService:
    """Obtiene la instancia singleton del servicio."""
    global _status_page
    if _status_page is None:
        _status_page = StatusPageService()
    return _status_page


# Alias
status_page = get_status_page
