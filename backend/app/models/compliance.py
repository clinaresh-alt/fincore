"""
Modelos de Cumplimiento Regulatorio - PLD/AML para Mexico.

Cumple con:
- Ley Federal para la Prevencion e Identificacion de Operaciones con Recursos
  de Procedencia Ilicita (LFPIORPI)
- Disposiciones de caracter general de la CNBV para activos virtuales
- Requisitos de la UIF (Unidad de Inteligencia Financiera)

Niveles de Verificacion KYC:
- Nivel 0: Sin verificar (solo registro)
- Nivel 1: Verificacion basica (INE, CURP) - Limite: $15,000 MXN/mes
- Nivel 2: Verificacion intermedia (+ comprobante domicilio) - Limite: $50,000 MXN/mes
- Nivel 3: Verificacion completa (+ ingresos, PEP check) - Sin limite
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Numeric,
    Text,
    ForeignKey,
    Enum as SQLEnum,
    JSON,
    Integer,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


# ============ Enums ============

class KYCLevel(str, Enum):
    """Niveles de verificacion KYC segun LFPIORPI."""
    LEVEL_0 = "level_0"  # Sin verificar
    LEVEL_1 = "level_1"  # Basico: INE + CURP
    LEVEL_2 = "level_2"  # Intermedio: + Comprobante domicilio
    LEVEL_3 = "level_3"  # Completo: + Ingresos + PEP check


class KYCStatus(str, Enum):
    """Estados del proceso KYC."""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class DocumentType(str, Enum):
    """Tipos de documentos para verificacion."""
    INE_FRONT = "ine_front"
    INE_BACK = "ine_back"
    PASSPORT = "passport"
    CURP = "curp"
    RFC = "rfc"
    PROOF_OF_ADDRESS = "proof_of_address"
    PROOF_OF_INCOME = "proof_of_income"
    BANK_STATEMENT = "bank_statement"
    TAX_RETURN = "tax_return"
    SELFIE = "selfie"
    SELFIE_WITH_ID = "selfie_with_id"
    COMPANY_DEED = "company_deed"  # Acta constitutiva
    POWER_OF_ATTORNEY = "power_of_attorney"  # Poder notarial


class DocumentStatus(str, Enum):
    """Estados de verificacion de documentos."""
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AlertType(str, Enum):
    """Tipos de alertas AML."""
    LARGE_TRANSACTION = "large_transaction"
    STRUCTURING = "structuring"  # Fraccionamiento
    RAPID_MOVEMENT = "rapid_movement"
    HIGH_RISK_COUNTRY = "high_risk_country"
    PEP_TRANSACTION = "pep_transaction"
    SANCTIONED_ENTITY = "sanctioned_entity"
    UNUSUAL_PATTERN = "unusual_pattern"
    THRESHOLD_EXCEEDED = "threshold_exceeded"
    DORMANT_ACCOUNT = "dormant_account"


class AlertSeverity(str, Enum):
    """Severidad de alertas AML."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Estados de alertas AML."""
    OPEN = "open"
    INVESTIGATING = "investigating"
    ESCALATED = "escalated"
    REPORTED = "reported"  # Reportado a UIF
    CLOSED_FALSE_POSITIVE = "closed_false_positive"
    CLOSED_CONFIRMED = "closed_confirmed"


class ReportType(str, Enum):
    """Tipos de reportes regulatorios."""
    ROS = "ros"  # Reporte de Operaciones Sospechosas
    ROI = "roi"  # Reporte de Operaciones Internas
    ROC = "roc"  # Reporte de Operaciones en Efectivo
    ROV = "rov"  # Reporte de Operaciones con Activos Virtuales


class RiskLevel(str, Enum):
    """Niveles de riesgo del cliente."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PROHIBITED = "prohibited"


# ============ Models ============

class KYCProfile(Base):
    """
    Perfil KYC completo del usuario.
    Vincula wallet con identidad real verificada.
    """
    __tablename__ = "kyc_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), unique=True, nullable=False)

    # Nivel y estado de verificacion
    kyc_level = Column(SQLEnum(KYCLevel), default=KYCLevel.LEVEL_0, nullable=False)
    status = Column(SQLEnum(KYCStatus), default=KYCStatus.PENDING, nullable=False)
    risk_level = Column(SQLEnum(RiskLevel), default=RiskLevel.MEDIUM, nullable=False)
    risk_score = Column(Integer, default=50)  # 0-100

    # Datos personales (encriptados en produccion)
    first_name = Column(String(100))
    last_name = Column(String(100))
    middle_name = Column(String(100))
    date_of_birth = Column(DateTime)
    nationality = Column(String(3))  # ISO 3166-1 alpha-3
    country_of_residence = Column(String(3))

    # Identificacion oficial
    curp = Column(String(18), unique=True)  # CURP mexicano
    rfc = Column(String(13))  # RFC mexicano
    ine_clave = Column(String(18))  # Clave de elector INE

    # Direccion
    street_address = Column(String(200))
    city = Column(String(100))
    state = Column(String(100))
    postal_code = Column(String(10))
    country = Column(String(3), default="MEX")

    # Informacion economica (Nivel 3)
    occupation = Column(String(100))
    employer = Column(String(200))
    monthly_income_range = Column(String(50))  # Rango de ingresos
    source_of_funds = Column(String(200))
    expected_monthly_volume = Column(Numeric(precision=18, scale=2))

    # PEP (Persona Politicamente Expuesta)
    is_pep = Column(Boolean, default=False)
    pep_position = Column(String(200))
    pep_relation = Column(String(100))  # Si es familiar de PEP

    # Listas de verificacion
    ofac_checked = Column(Boolean, default=False)
    ofac_check_date = Column(DateTime)
    ofac_clear = Column(Boolean)

    pep_checked = Column(Boolean, default=False)
    pep_check_date = Column(DateTime)

    adverse_media_checked = Column(Boolean, default=False)
    adverse_media_check_date = Column(DateTime)
    adverse_media_clear = Column(Boolean)

    # Limites de transaccion basados en nivel KYC
    daily_limit = Column(Numeric(precision=18, scale=2), default=Decimal("15000.00"))
    monthly_limit = Column(Numeric(precision=18, scale=2), default=Decimal("50000.00"))

    # Volumenes acumulados (para monitoreo)
    current_month_volume = Column(Numeric(precision=18, scale=2), default=Decimal("0"))
    total_volume = Column(Numeric(precision=18, scale=2), default=Decimal("0"))

    # Metadata
    verified_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    verified_at = Column(DateTime)
    rejection_reason = Column(Text)
    notes = Column(Text)

    # Fechas
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime)  # KYC expira y requiere renovacion

    # Relaciones
    user = relationship("User", foreign_keys=[user_id], backref="kyc_profile")
    documents = relationship("KYCDocument", back_populates="kyc_profile", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_kyc_profiles_curp", "curp"),
        Index("ix_kyc_profiles_status", "status"),
        Index("ix_kyc_profiles_risk_level", "risk_level"),
    )


class KYCDocument(Base):
    """Documentos de verificacion KYC."""
    __tablename__ = "kyc_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kyc_profile_id = Column(UUID(as_uuid=True), ForeignKey("kyc_profiles.id"), nullable=False)

    document_type = Column(SQLEnum(DocumentType), nullable=False)
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False)

    # Archivo
    file_path = Column(String(500), nullable=False)  # Ruta encriptada
    file_hash = Column(String(64))  # SHA-256 del archivo
    file_size = Column(Integer)
    mime_type = Column(String(100))

    # Datos extraidos (OCR/verificacion)
    extracted_data = Column(JSON)  # Datos extraidos del documento
    verification_result = Column(JSON)  # Resultado de verificacion
    confidence_score = Column(Numeric(precision=5, scale=2))  # Score de confianza OCR

    # Verificacion
    verified_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    verified_at = Column(DateTime)
    rejection_reason = Column(Text)

    # Validez
    issue_date = Column(DateTime)
    expiry_date = Column(DateTime)
    is_expired = Column(Boolean, default=False)

    # Fechas
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    kyc_profile = relationship("KYCProfile", back_populates="documents")

    __table_args__ = (
        Index("ix_kyc_documents_type_status", "document_type", "status"),
    )


class AMLAlert(Base):
    """
    Alertas de Prevencion de Lavado de Dinero.
    Generadas automaticamente por el sistema de monitoreo.
    """
    __tablename__ = "aml_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Usuario/transaccion relacionada
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    transaction_id = Column(UUID(as_uuid=True))  # ID de transaccion si aplica
    wallet_address = Column(String(100))

    # Tipo y severidad
    alert_type = Column(SQLEnum(AlertType), nullable=False)
    severity = Column(SQLEnum(AlertSeverity), nullable=False)
    status = Column(SQLEnum(AlertStatus), default=AlertStatus.OPEN, nullable=False)

    # Detalles
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    amount = Column(Numeric(precision=18, scale=2))
    currency = Column(String(10), default="MXN")

    # Regla que genero la alerta
    rule_id = Column(String(50))
    rule_name = Column(String(200))
    rule_parameters = Column(JSON)

    # Datos adicionales
    extra_data = Column(JSON)  # Contexto adicional
    related_alerts = Column(JSON)  # IDs de alertas relacionadas

    # Investigacion
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    investigation_notes = Column(Text)
    investigation_started_at = Column(DateTime)

    # Resolucion
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)
    false_positive = Column(Boolean)

    # Reporte a UIF
    reported_to_uif = Column(Boolean, default=False)
    uif_report_id = Column(UUID(as_uuid=True), ForeignKey("regulatory_reports.id"))

    # Fechas
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_aml_alerts_user_status", "user_id", "status"),
        Index("ix_aml_alerts_severity", "severity"),
        Index("ix_aml_alerts_detected_at", "detected_at"),
    )


class AMLRule(Base):
    """Reglas de deteccion AML configurables."""
    __tablename__ = "aml_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String(200), nullable=False)
    description = Column(Text)
    alert_type = Column(SQLEnum(AlertType), nullable=False)
    severity = Column(SQLEnum(AlertSeverity), nullable=False)

    # Configuracion de la regla
    is_active = Column(Boolean, default=True)
    parameters = Column(JSON, nullable=False)
    # Ejemplo parameters:
    # {
    #   "threshold_amount": 50000,
    #   "time_window_hours": 24,
    #   "min_transactions": 3
    # }

    # Estadisticas
    triggers_count = Column(Integer, default=0)
    false_positive_count = Column(Integer, default=0)
    last_triggered_at = Column(DateTime)

    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RegulatoryReport(Base):
    """
    Reportes regulatorios para la UIF.
    ROS, ROI, ROC, ROV segun LFPIORPI.
    """
    __tablename__ = "regulatory_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    report_type = Column(SQLEnum(ReportType), nullable=False)
    reference_number = Column(String(50), unique=True)  # Folio interno

    # Periodo del reporte
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Contenido
    report_data = Column(JSON, nullable=False)
    xml_content = Column(Text)  # XML para envio a UIF

    # Transacciones incluidas
    transactions_count = Column(Integer, default=0)
    total_amount = Column(Numeric(precision=18, scale=2))

    # Alertas relacionadas
    related_alerts = Column(JSON)  # IDs de alertas incluidas

    # Estado de envio
    status = Column(String(50), default="draft")  # draft, ready, submitted, accepted, rejected
    submitted_at = Column(DateTime)
    uif_confirmation = Column(String(100))  # Numero de confirmacion UIF
    uif_response = Column(JSON)

    # Metadata
    generated_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    approved_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    approved_at = Column(DateTime)

    # Fechas
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_regulatory_reports_type_period", "report_type", "period_start"),
    )


class TransactionMonitor(Base):
    """
    Registro de transacciones para monitoreo AML.
    Cada transaccion es analizada contra reglas AML.
    """
    __tablename__ = "transaction_monitors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Usuario
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)

    # Transaccion
    transaction_type = Column(String(50), nullable=False)  # deposit, withdrawal, transfer, investment
    amount = Column(Numeric(precision=18, scale=2), nullable=False)
    currency = Column(String(10), default="MXN")

    # Origen/Destino
    source_type = Column(String(50))  # bank, wallet, exchange
    source_identifier = Column(String(200))  # Cuenta bancaria, wallet address
    destination_type = Column(String(50))
    destination_identifier = Column(String(200))

    # Blockchain (si aplica)
    blockchain_network = Column(String(50))
    tx_hash = Column(String(100))

    # Analisis AML
    risk_score = Column(Integer)  # 0-100
    rules_triggered = Column(JSON)  # IDs de reglas activadas
    alerts_generated = Column(JSON)  # IDs de alertas generadas

    # Ubicacion/IP
    ip_address = Column(String(50))
    country_code = Column(String(3))
    device_fingerprint = Column(String(200))

    # Estado
    status = Column(String(50), default="completed")
    flagged = Column(Boolean, default=False)
    reviewed = Column(Boolean, default=False)

    # Fechas
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_transaction_monitors_user_date", "user_id", "executed_at"),
        Index("ix_transaction_monitors_flagged", "flagged"),
    )


class SanctionsList(Base):
    """
    Listas de sanciones (OFAC, ONU, EU, Mexico).
    Para verificacion contra entidades sancionadas.
    """
    __tablename__ = "sanctions_lists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    list_source = Column(String(50), nullable=False)  # OFAC, UN, EU, MEXICO_UIF
    entity_type = Column(String(50))  # individual, organization

    # Identificacion
    name = Column(String(500), nullable=False)
    aliases = Column(JSON)  # Lista de alias

    # Datos de identificacion
    identifiers = Column(JSON)  # DNI, passport, etc.
    date_of_birth = Column(DateTime)
    nationality = Column(String(3))

    # Razon de sancion
    reason = Column(Text)
    programs = Column(JSON)  # Programas de sanciones aplicables

    # Fechas
    listed_date = Column(DateTime)
    delisted_date = Column(DateTime)
    is_active = Column(Boolean, default=True)

    # Metadata
    source_url = Column(String(500))
    last_updated = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_sanctions_lists_name", "name"),
        Index("ix_sanctions_lists_source", "list_source", "is_active"),
    )


class AssetValuation(Base):
    """
    Valuacion de activos virtuales segun criterios CNBV.
    Registro historico para cumplimiento contable.
    """
    __tablename__ = "asset_valuations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Activo
    asset_type = Column(String(50), nullable=False)  # token, cryptocurrency, nft
    asset_id = Column(UUID(as_uuid=True))  # ID del token si aplica
    asset_symbol = Column(String(20))

    # Valuacion
    valuation_date = Column(DateTime, nullable=False)
    unit_price_mxn = Column(Numeric(precision=18, scale=8), nullable=False)
    unit_price_usd = Column(Numeric(precision=18, scale=8))
    total_units = Column(Numeric(precision=18, scale=8))
    total_value_mxn = Column(Numeric(precision=18, scale=2))

    # Metodologia CNBV
    valuation_method = Column(String(100))  # mark_to_market, cost, fair_value
    price_source = Column(String(200))  # Exchange, oracle, etc.

    # Tipo de cambio usado
    usd_mxn_rate = Column(Numeric(precision=10, scale=4))
    rate_source = Column(String(100))  # Banxico, etc.

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_asset_valuations_asset_date", "asset_id", "valuation_date"),
    )
