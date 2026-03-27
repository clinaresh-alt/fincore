"""
Schemas Pydantic para Compliance Screening (Chainalysis/Elliptic).

Define los DTOs para:
- Solicitudes de screening de direcciones blockchain
- Respuestas de analisis de riesgo
- Alertas y reportes de cumplimiento
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


# ============ Enums ============

class RiskLevel(str, Enum):
    """Nivel de riesgo de una direccion."""
    SEVERE = "severe"       # 90-100: Bloquear inmediatamente
    HIGH = "high"           # 70-89: Requiere revision manual
    MEDIUM = "medium"       # 40-69: Monitoreo aumentado
    LOW = "low"             # 10-39: Normal
    MINIMAL = "minimal"     # 0-9: Sin riesgo detectado


class RiskCategory(str, Enum):
    """Categorias de riesgo detectadas."""
    SANCTIONS = "sanctions"                 # Lista OFAC/ONU
    DARKNET_MARKET = "darknet_market"       # Mercados ilegales
    MIXER = "mixer"                         # Servicios de mezcla
    RANSOMWARE = "ransomware"               # Direcciones de ransomware
    STOLEN_FUNDS = "stolen_funds"           # Fondos robados
    TERRORISM = "terrorism"                 # Financiamiento terrorismo
    SCAM = "scam"                           # Estafas conocidas
    CHILD_EXPLOITATION = "child_exploitation"  # CSAM
    HIGH_RISK_EXCHANGE = "high_risk_exchange"  # Exchanges sin KYC
    GAMBLING = "gambling"                   # Juego ilegal
    DRUG_TRAFFICKING = "drug_trafficking"   # Narcotrafico
    FRAUD = "fraud"                         # Fraude
    PEP = "pep"                             # Persona Expuesta Politicamente
    UNKNOWN = "unknown"                     # No categorizado


class ScreeningStatus(str, Enum):
    """Estado del screening."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"


class ScreeningAction(str, Enum):
    """Accion recomendada tras el screening."""
    APPROVE = "approve"           # Proceder con la transaccion
    REVIEW = "review"             # Revision manual requerida
    REJECT = "reject"             # Rechazar transaccion
    BLOCK = "block"               # Bloquear usuario/direccion
    REPORT = "report"             # Reportar a autoridades (SAR)
    ENHANCED_DUE_DILIGENCE = "edd"  # Due diligence mejorado


class BlockchainNetwork(str, Enum):
    """Redes blockchain soportadas."""
    POLYGON = "polygon"
    ETHEREUM = "ethereum"
    ARBITRUM = "arbitrum"
    BASE = "base"
    BITCOIN = "bitcoin"
    TRON = "tron"


# ============ Request Schemas ============

class AddressScreeningRequest(BaseModel):
    """Solicitud de screening de direccion blockchain."""
    address: str = Field(..., min_length=26, max_length=64, description="Direccion a analizar")
    network: BlockchainNetwork = Field(..., description="Red blockchain")
    user_id: Optional[str] = Field(None, description="ID del usuario asociado")
    remittance_id: Optional[str] = Field(None, description="ID de remesa asociada")
    amount_usd: Optional[Decimal] = Field(None, ge=0, description="Monto en USD de la transaccion")
    direction: str = Field("inbound", description="Direccion del flujo: inbound/outbound")

    class Config:
        json_schema_extra = {
            "example": {
                "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0Ab12",
                "network": "polygon",
                "user_id": "user_123",
                "remittance_id": "rem_456",
                "amount_usd": 1500.00,
                "direction": "inbound"
            }
        }


class TransactionScreeningRequest(BaseModel):
    """Solicitud de screening de transaccion."""
    tx_hash: str = Field(..., min_length=64, max_length=66, description="Hash de la transaccion")
    network: BlockchainNetwork = Field(..., description="Red blockchain")
    from_address: str = Field(..., description="Direccion origen")
    to_address: str = Field(..., description="Direccion destino")
    amount: Decimal = Field(..., ge=0, description="Monto de la transaccion")
    token_symbol: str = Field(..., description="Simbolo del token (USDC, ETH, etc.)")
    remittance_id: Optional[str] = Field(None, description="ID de remesa asociada")


class BatchScreeningRequest(BaseModel):
    """Solicitud de screening en lote."""
    addresses: List[AddressScreeningRequest] = Field(..., max_length=100)
    priority: str = Field("normal", description="Prioridad: high, normal, low")


# ============ Response Schemas ============

class RiskIndicator(BaseModel):
    """Indicador de riesgo individual."""
    category: RiskCategory
    severity: int = Field(..., ge=0, le=100, description="Severidad 0-100")
    description: str
    source: str = Field(..., description="Fuente del dato (chainalysis, elliptic, etc.)")
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    confidence: float = Field(..., ge=0, le=1, description="Confianza en el resultado 0-1")

    class Config:
        json_schema_extra = {
            "example": {
                "category": "mixer",
                "severity": 75,
                "description": "Direccion asociada con Tornado Cash",
                "source": "chainalysis",
                "confidence": 0.95
            }
        }


class ExposureDetail(BaseModel):
    """Detalle de exposicion a entidades de riesgo."""
    entity_name: str
    entity_type: str
    category: RiskCategory
    exposure_amount_usd: Decimal
    exposure_percentage: float
    transaction_count: int
    first_transaction: Optional[datetime] = None
    last_transaction: Optional[datetime] = None


class AddressScreeningResponse(BaseModel):
    """Respuesta de screening de direccion."""
    screening_id: str
    address: str
    network: BlockchainNetwork
    status: ScreeningStatus

    # Puntuacion de riesgo
    risk_score: int = Field(..., ge=0, le=100, description="Score de riesgo 0-100")
    risk_level: RiskLevel

    # Indicadores detectados
    risk_indicators: List[RiskIndicator] = Field(default_factory=list)

    # Exposicion a entidades
    direct_exposure: List[ExposureDetail] = Field(default_factory=list)
    indirect_exposure: List[ExposureDetail] = Field(default_factory=list)

    # Accion recomendada
    recommended_action: ScreeningAction
    action_reason: str

    # Metadatos de la direccion
    address_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    cluster_info: Optional[Dict[str, Any]] = None  # Info de clustering

    # Timestamps
    screened_at: datetime
    data_as_of: datetime  # Fecha de los datos de Chainalysis

    # Flags regulatorios
    is_sanctioned: bool = False
    requires_sar: bool = False  # Suspicious Activity Report
    pep_match: bool = False

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "screening_id": "scr_abc123",
                "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0Ab12",
                "network": "polygon",
                "status": "completed",
                "risk_score": 25,
                "risk_level": "low",
                "risk_indicators": [],
                "recommended_action": "approve",
                "action_reason": "Sin indicadores de riesgo detectados",
                "screened_at": "2024-01-15T10:30:00Z",
                "data_as_of": "2024-01-15T10:00:00Z",
                "is_sanctioned": False,
                "requires_sar": False
            }
        }


class TransactionScreeningResponse(BaseModel):
    """Respuesta de screening de transaccion."""
    screening_id: str
    tx_hash: str
    network: BlockchainNetwork
    status: ScreeningStatus

    # Analisis de origen y destino
    from_address_risk: AddressScreeningResponse
    to_address_risk: AddressScreeningResponse

    # Riesgo combinado
    combined_risk_score: int = Field(..., ge=0, le=100)
    combined_risk_level: RiskLevel
    recommended_action: ScreeningAction

    # Analisis de flujo
    tainted_amount_usd: Optional[Decimal] = None
    taint_percentage: Optional[float] = None

    screened_at: datetime

    class Config:
        from_attributes = True


class BatchScreeningResponse(BaseModel):
    """Respuesta de screening en lote."""
    batch_id: str
    total_addresses: int
    completed: int
    failed: int
    results: List[AddressScreeningResponse]

    # Resumen
    high_risk_count: int
    blocked_count: int
    requires_review_count: int

    processed_at: datetime


# ============ Alert/Report Schemas ============

class ComplianceAlert(BaseModel):
    """Alerta de cumplimiento."""
    alert_id: str
    alert_type: str  # screening_failed, high_risk_detected, sanctions_match, etc.
    severity: RiskLevel

    # Contexto
    address: Optional[str] = None
    user_id: Optional[str] = None
    remittance_id: Optional[str] = None
    screening_id: Optional[str] = None

    # Detalles
    title: str
    description: str
    risk_indicators: List[RiskIndicator] = Field(default_factory=list)

    # Accion
    recommended_action: ScreeningAction
    auto_action_taken: Optional[str] = None

    # Estado
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None

    created_at: datetime

    class Config:
        from_attributes = True


class SuspiciousActivityReport(BaseModel):
    """Reporte de Actividad Sospechosa (SAR) para CNBV."""
    report_id: str
    report_type: str = "SAR"

    # Sujeto del reporte
    user_id: str
    user_name: str
    user_rfc: Optional[str] = None
    user_curp: Optional[str] = None

    # Transacciones sospechosas
    remittance_ids: List[str]
    total_amount_usd: Decimal
    total_amount_mxn: Decimal

    # Indicadores
    risk_indicators: List[RiskIndicator]
    suspicious_patterns: List[str]

    # Analisis
    narrative: str
    recommendation: str

    # Metadatos
    generated_at: datetime
    generated_by: str
    submitted_to_cnbv: bool = False
    cnbv_reference: Optional[str] = None
    submitted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ Configuration Schemas ============

class ScreeningThresholds(BaseModel):
    """Umbrales de screening configurables."""
    auto_approve_max_score: int = Field(30, ge=0, le=100)
    review_min_score: int = Field(31, ge=0, le=100)
    auto_reject_min_score: int = Field(70, ge=0, le=100)
    block_min_score: int = Field(90, ge=0, le=100)

    # Umbrales por monto
    enhanced_screening_amount_usd: Decimal = Field(Decimal("3000"))
    auto_report_amount_usd: Decimal = Field(Decimal("10000"))

    # Categorias que siempre bloquean
    always_block_categories: List[RiskCategory] = Field(
        default=[
            RiskCategory.SANCTIONS,
            RiskCategory.TERRORISM,
            RiskCategory.CHILD_EXPLOITATION,
            RiskCategory.RANSOMWARE,
        ]
    )


class ScreeningStats(BaseModel):
    """Estadisticas de screening."""
    period_start: datetime
    period_end: datetime

    total_screenings: int
    approved: int
    rejected: int
    blocked: int
    pending_review: int

    average_risk_score: float
    high_risk_percentage: float

    # Por categoria
    by_category: Dict[str, int]
    by_network: Dict[str, int]

    # Tiempos
    average_screening_time_ms: float

    class Config:
        from_attributes = True
