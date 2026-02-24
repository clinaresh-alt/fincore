"""
Modelos de Evaluacion de Factibilidad y Sistema de Alertas.
Scorecard para evaluacion cualitativa de proyectos.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime,
    Text, ForeignKey, Enum as SQLEnum, Numeric
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class AlertType(str, enum.Enum):
    """Tipos de alertas del sistema."""
    RIESGO = "Riesgo"
    FISCAL = "Fiscal"
    RENDIMIENTO = "Rendimiento"
    OPORTUNIDAD = "Oportunidad"
    VENCIMIENTO = "Vencimiento"


class AlertSeverity(str, enum.Enum):
    """Severidad de las alertas."""
    CRITICO = "Critico"
    ADVERTENCIA = "Advertencia"
    INFORMATIVO = "Informativo"


class FeasibilityStudy(Base):
    """
    Estudio de factibilidad cualitativo (Scorecard).
    Evalua aspectos no financieros del proyecto.
    """
    __tablename__ = "estudios_factibilidad"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proyecto_id = Column(
        UUID(as_uuid=True),
        ForeignKey("proyectos.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    # === FACTIBILIDAD TECNICA Y OPERATIVA ===
    # Capacidad instalada (1-10)
    score_capacidad_instalada = Column(Integer, default=5)
    notas_capacidad = Column(Text, nullable=True)

    # Equipo gestor (1-10)
    score_equipo_gestor = Column(Integer, default=5)
    experiencia_equipo_anos = Column(Integer, nullable=True)
    proyectos_previos_exitosos = Column(Integer, default=0)
    notas_equipo = Column(Text, nullable=True)

    # Tecnologia y procesos (1-10)
    score_tecnologia = Column(Integer, default=5)
    tiene_patentes = Column(Boolean, default=False)
    notas_tecnologia = Column(Text, nullable=True)

    # === ANALISIS DE MERCADO ===
    # TAM/SAM/SOM en millones
    tam_millones = Column(Numeric(18, 2), nullable=True)  # Total Addressable Market
    sam_millones = Column(Numeric(18, 2), nullable=True)  # Serviceable Addressable Market
    som_millones = Column(Numeric(18, 2), nullable=True)  # Serviceable Obtainable Market

    # Competencia (1-10, mayor es mejor posicion)
    score_posicion_competitiva = Column(Integer, default=5)
    competidores_principales = Column(JSONB, nullable=True)
    # Estructura: [{"nombre": "...", "fortaleza": "...", "debilidad": "..."}]

    barreras_entrada = Column(Text, nullable=True)
    ventaja_competitiva = Column(Text, nullable=True)

    # === FACTIBILIDAD LEGAL Y TRIBUTARIA ===
    tiene_licencias_requeridas = Column(Boolean, default=False)
    licencias_pendientes = Column(Text, nullable=True)

    score_cumplimiento_normativo = Column(Integer, default=5)
    riesgos_legales_identificados = Column(Text, nullable=True)

    # Incentivos fiscales aplicables
    incentivos_fiscales = Column(JSONB, nullable=True)
    # Estructura: [{"tipo": "...", "beneficio": "...", "vigencia": "..."}]

    tasa_impositiva_efectiva = Column(Numeric(5, 4), nullable=True)

    # === FACTIBILIDAD AMBIENTAL Y SOCIAL ===
    impacto_ambiental = Column(String(50), nullable=True)  # Bajo, Medio, Alto
    requiere_eia = Column(Boolean, default=False)  # Estudio Impacto Ambiental
    score_esg = Column(Integer, nullable=True)  # Environmental, Social, Governance

    # === SCORES CONSOLIDADOS ===
    score_tecnico_total = Column(Numeric(5, 2), nullable=True)  # Promedio tecnico
    score_mercado_total = Column(Numeric(5, 2), nullable=True)  # Promedio mercado
    score_legal_total = Column(Numeric(5, 2), nullable=True)    # Promedio legal
    score_factibilidad_global = Column(Numeric(5, 2), nullable=True)  # Score final 0-100

    # Recomendacion del sistema
    recomendacion_automatica = Column(String(50), nullable=True)
    # "Aprobar", "Revisar", "Rechazar"

    # Metadatos
    evaluador_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    fecha_evaluacion = Column(DateTime(timezone=True), default=datetime.utcnow)
    notas_generales = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    def calcular_scores(self):
        """Calcula scores consolidados."""
        # Score tecnico (promedio de capacidad, equipo, tecnologia)
        tecnico = [
            self.score_capacidad_instalada or 5,
            self.score_equipo_gestor or 5,
            self.score_tecnologia or 5
        ]
        self.score_tecnico_total = Decimal(sum(tecnico) / len(tecnico))

        # Score mercado
        mercado = [self.score_posicion_competitiva or 5]
        self.score_mercado_total = Decimal(sum(mercado) / len(mercado))

        # Score legal
        legal = [self.score_cumplimiento_normativo or 5]
        if self.tiene_licencias_requeridas:
            legal.append(8)
        self.score_legal_total = Decimal(sum(legal) / len(legal))

        # Score global (ponderado)
        self.score_factibilidad_global = Decimal(
            (float(self.score_tecnico_total) * 0.4 +
             float(self.score_mercado_total) * 0.35 +
             float(self.score_legal_total) * 0.25) * 10
        )

        # Recomendacion automatica
        if self.score_factibilidad_global >= 70:
            self.recomendacion_automatica = "Aprobar"
        elif self.score_factibilidad_global >= 50:
            self.recomendacion_automatica = "Revisar"
        else:
            self.recomendacion_automatica = "Rechazar"

    def __repr__(self):
        return f"<FeasibilityStudy Score={self.score_factibilidad_global}>"


class AlertConfig(Base):
    """
    Configuracion de alertas por usuario.
    Define umbrales y canales de notificacion.
    """
    __tablename__ = "alertas_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )

    tipo_alerta = Column(
        SQLEnum(AlertType, name="alert_type_enum"),
        nullable=False
    )

    # Umbrales
    umbral_minimo = Column(Numeric(18, 4), nullable=True)  # Ej: TIR < 10%
    umbral_maximo = Column(Numeric(18, 4), nullable=True)  # Ej: Riesgo > 70%

    # Canales de envio
    canal_email = Column(Boolean, default=True)
    canal_push = Column(Boolean, default=True)
    canal_sms = Column(Boolean, default=False)
    canal_whatsapp = Column(Boolean, default=False)

    activa = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AlertConfig {self.tipo_alerta} User={self.usuario_id}>"


class Alert(Base):
    """
    Alertas generadas por el sistema.
    Registro historico de notificaciones.
    """
    __tablename__ = "alertas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    usuario_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )

    proyecto_id = Column(
        UUID(as_uuid=True),
        ForeignKey("proyectos.id", ondelete="SET NULL"),
        nullable=True
    )

    tipo = Column(
        SQLEnum(AlertType, name="alert_type_enum"),
        nullable=False
    )

    severidad = Column(
        SQLEnum(AlertSeverity, name="alert_severity_enum"),
        default=AlertSeverity.INFORMATIVO
    )

    titulo = Column(String(255), nullable=False)
    mensaje = Column(Text, nullable=False)

    # Datos adicionales
    datos = Column(JSONB, nullable=True)
    # Estructura variable segun tipo de alerta

    # Estado
    leida = Column(Boolean, default=False)
    fecha_lectura = Column(DateTime(timezone=True), nullable=True)

    # Accion tomada
    accion_requerida = Column(Boolean, default=False)
    accion_completada = Column(Boolean, default=False)
    fecha_accion = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    def __repr__(self):
        return f"<Alert {self.tipo}: {self.titulo}>"


class SensitivityAnalysis(Base):
    """
    Registro de analisis de sensibilidad ejecutados.
    Almacena resultados de simulaciones.
    """
    __tablename__ = "analisis_sensibilidad"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proyecto_id = Column(
        UUID(as_uuid=True),
        ForeignKey("proyectos.id", ondelete="CASCADE"),
        nullable=False
    )

    # Parametros de la simulacion
    variable_estresada = Column(String(50), nullable=False)
    # "ingresos", "costos", "tasa_descuento", "inversion_inicial"

    variacion_aplicada = Column(Numeric(5, 4), nullable=False)  # -0.20 a +0.20

    # Resultados
    van_resultante = Column(Numeric(18, 2), nullable=True)
    tir_resultante = Column(Numeric(7, 4), nullable=True)
    payback_resultante = Column(Numeric(5, 2), nullable=True)

    # Punto de equilibrio
    punto_equilibrio_variable = Column(Numeric(18, 4), nullable=True)
    margen_seguridad = Column(Numeric(5, 4), nullable=True)

    # Escenario
    escenario = Column(String(20), nullable=False)  # "Pesimista", "Base", "Optimista"

    # Estado de viabilidad resultante
    estado_viabilidad = Column(String(50), nullable=True)
    # "Viable", "Riesgo Moderado", "Riesgo Alto", "No Viable"

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    def __repr__(self):
        return f"<SensitivityAnalysis {self.escenario} VAN={self.van_resultante}>"
