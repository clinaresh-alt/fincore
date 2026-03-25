"""
Modelo de Configuracion del Sistema.
Almacena configuraciones sensibles cifradas (API keys, etc.).
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.core.database import Base


class ConfigCategory(str, enum.Enum):
    """Categorias de configuracion."""
    AI_INTEGRATION = "ai_integration"
    BLOCKCHAIN = "blockchain"
    SECURITY = "security"
    NOTIFICATIONS = "notifications"
    EXTERNAL_APIS = "external_apis"
    SYSTEM = "system"
    GENERAL = "general"


class SystemConfig(Base):
    """
    Tabla de configuraciones del sistema.
    Las API keys se almacenan cifradas.
    """
    __tablename__ = "system_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identificador unico de la configuracion
    config_key = Column(String(100), unique=True, nullable=False, index=True)

    # Valor (puede ser cifrado para datos sensibles)
    config_value = Column(Text, nullable=True)

    # Metadatos
    category = Column(
        SQLEnum(ConfigCategory, name="config_category_enum"),
        default=ConfigCategory.GENERAL,
        nullable=False
    )
    description = Column(String(500), nullable=True)

    # Indica si el valor esta cifrado
    is_encrypted = Column(Boolean, default=False)

    # Indica si la configuracion esta activa
    is_active = Column(Boolean, default=True)

    # Auditoria
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(UUID(as_uuid=True), nullable=True)

    def __repr__(self):
        return f"<SystemConfig {self.config_key}>"


# Configuraciones predefinidas del sistema
SYSTEM_CONFIG_DEFINITIONS = {
    "anthropic_api_key": {
        "category": ConfigCategory.AI_INTEGRATION,
        "description": "API Key de Anthropic para analisis de documentos con IA",
        "is_encrypted": True
    },
    "openai_api_key": {
        "category": ConfigCategory.AI_INTEGRATION,
        "description": "API Key de OpenAI (alternativa)",
        "is_encrypted": True
    },
    "ai_analysis_enabled": {
        "category": ConfigCategory.AI_INTEGRATION,
        "description": "Habilitar analisis de documentos con IA",
        "is_encrypted": False
    },
    "max_pdf_size_mb": {
        "category": ConfigCategory.AI_INTEGRATION,
        "description": "Tamano maximo de PDF para analisis (MB)",
        "is_encrypted": False
    },
    "smtp_password": {
        "category": ConfigCategory.NOTIFICATIONS,
        "description": "Password del servidor SMTP",
        "is_encrypted": True
    },
    "tax_api_key": {
        "category": ConfigCategory.EXTERNAL_APIS,
        "description": "API Key para integracion fiscal",
        "is_encrypted": True
    },
    # Blockchain configs
    "blockchain_walletconnect_project_id": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "WalletConnect Project ID para conexion de wallets",
        "is_encrypted": False
    },
    "blockchain_investment_contract": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "Direccion del contrato de inversion",
        "is_encrypted": False
    },
    "blockchain_kyc_contract": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "Direccion del contrato de KYC",
        "is_encrypted": False
    },
    "blockchain_dividends_contract": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "Direccion del contrato de dividendos",
        "is_encrypted": False
    },
    "blockchain_token_factory_contract": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "Direccion del contrato Token Factory",
        "is_encrypted": False
    },
    "blockchain_default_network": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "Red blockchain por defecto (polygon, ethereum, arbitrum, base)",
        "is_encrypted": False
    },
    "blockchain_is_testnet": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "Modo testnet habilitado",
        "is_encrypted": False
    },
    "blockchain_rpc_polygon": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "RPC URL para Polygon",
        "is_encrypted": False
    },
    "blockchain_rpc_ethereum": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "RPC URL para Ethereum",
        "is_encrypted": False
    },
    "blockchain_rpc_arbitrum": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "RPC URL para Arbitrum",
        "is_encrypted": False
    },
    "blockchain_rpc_base": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "RPC URL para Base",
        "is_encrypted": False
    },
    "blockchain_rpc_polygon_amoy": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "RPC URL para Polygon Amoy (testnet)",
        "is_encrypted": False
    },
    "blockchain_rpc_sepolia": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "RPC URL para Sepolia (testnet)",
        "is_encrypted": False
    },
    "blockchain_api_polygonscan": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "API Key de Polygonscan",
        "is_encrypted": True
    },
    "blockchain_api_etherscan": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "API Key de Etherscan",
        "is_encrypted": True
    },
    "blockchain_api_arbiscan": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "API Key de Arbiscan",
        "is_encrypted": True
    },
    "blockchain_api_basescan": {
        "category": ConfigCategory.BLOCKCHAIN,
        "description": "API Key de Basescan",
        "is_encrypted": True
    },
    # System configs
    "system_app_name": {
        "category": ConfigCategory.SYSTEM,
        "description": "Nombre de la aplicacion",
        "is_encrypted": False
    },
    "system_app_version": {
        "category": ConfigCategory.SYSTEM,
        "description": "Version de la aplicacion",
        "is_encrypted": False
    },
    "system_debug_mode": {
        "category": ConfigCategory.SYSTEM,
        "description": "Modo debug habilitado",
        "is_encrypted": False
    },
    "system_api_timeout": {
        "category": ConfigCategory.SYSTEM,
        "description": "Timeout del API en ms",
        "is_encrypted": False
    },
    "system_max_upload_size": {
        "category": ConfigCategory.SYSTEM,
        "description": "Tamano maximo de archivo (MB)",
        "is_encrypted": False
    },
    "system_session_timeout": {
        "category": ConfigCategory.SYSTEM,
        "description": "Timeout de sesion (minutos)",
        "is_encrypted": False
    },
    "system_kyc_required": {
        "category": ConfigCategory.SYSTEM,
        "description": "KYC obligatorio para invertir",
        "is_encrypted": False
    },
    "system_min_investment": {
        "category": ConfigCategory.SYSTEM,
        "description": "Inversion minima (MXN)",
        "is_encrypted": False
    },
    "system_max_investment": {
        "category": ConfigCategory.SYSTEM,
        "description": "Inversion maxima (MXN)",
        "is_encrypted": False
    }
}
