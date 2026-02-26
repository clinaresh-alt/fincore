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
    SECURITY = "security"
    NOTIFICATIONS = "notifications"
    EXTERNAL_APIS = "external_apis"
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
    }
}
