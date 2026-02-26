"""
Endpoints de Administracion del Sistema.
Gestion de configuraciones, API keys, y estado del sistema.
Solo accesible para usuarios con rol Admin.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import anthropic
import os

from app.core.database import get_db
from app.core.config import settings
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User, UserRole
from app.models.system_config import SystemConfig, ConfigCategory, SYSTEM_CONFIG_DEFINITIONS
from app.models.audit import AuditLog, AuditAction

router = APIRouter(prefix="/admin", tags=["Administracion"])


# === Schemas ===
class ConfigValueUpdate(BaseModel):
    """Schema para actualizar un valor de configuracion."""
    value: str = Field(..., description="Nuevo valor de la configuracion")
    skip_validation: bool = Field(default=False, description="Omitir validacion de API key")


class ConfigResponse(BaseModel):
    """Schema de respuesta para una configuracion."""
    key: str
    value: Optional[str] = None
    category: str
    description: Optional[str] = None
    is_encrypted: bool
    is_active: bool
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AIStatusResponse(BaseModel):
    """Estado de la integracion de IA."""
    anthropic_configured: bool
    anthropic_valid: bool
    ai_analysis_enabled: bool
    error_message: Optional[str] = None


class SystemStatusResponse(BaseModel):
    """Estado general del sistema."""
    version: str
    environment: str
    database_connected: bool
    ai_integration: AIStatusResponse
    total_configs: int


# === Helpers ===
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Verifica que el usuario tenga rol de Admin."""
    if current_user.rol != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de Administrador"
        )
    return current_user


def mask_api_key(key: str) -> str:
    """Enmascara una API key mostrando solo los ultimos 4 caracteres."""
    if not key or len(key) < 8:
        return "****"
    return f"{'*' * (len(key) - 4)}{key[-4:]}"


def validate_anthropic_key(api_key: str) -> tuple[bool, Optional[str]]:
    """Valida una API key de Anthropic intentando una llamada simple."""
    if not api_key:
        return False, "API key vacia"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        # Hacer una llamada minima para validar la key
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}]
        )
        return True, None
    except anthropic.AuthenticationError:
        return False, "API key invalida o expirada"
    except anthropic.RateLimitError:
        return True, None  # Key valida pero rate limited
    except Exception as e:
        return False, f"Error de conexion: {str(e)}"


# === Endpoints ===
@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Obtiene el estado general del sistema.
    Incluye estado de integraciones y configuraciones.
    """
    # Verificar conexion a BD
    try:
        db.execute("SELECT 1")
        db_connected = True
    except Exception:
        db_connected = False

    # Verificar configuracion de IA
    anthropic_key = get_config_value(db, "anthropic_api_key")
    ai_enabled = get_config_value(db, "ai_analysis_enabled")

    ai_status = AIStatusResponse(
        anthropic_configured=bool(anthropic_key),
        anthropic_valid=False,
        ai_analysis_enabled=ai_enabled == "true" if ai_enabled else False,
        error_message=None
    )

    if anthropic_key:
        is_valid, error = validate_anthropic_key(anthropic_key)
        ai_status.anthropic_valid = is_valid
        ai_status.error_message = error

    # Contar configuraciones
    total_configs = db.query(SystemConfig).count()

    return SystemStatusResponse(
        version=settings.APP_VERSION,
        environment="development" if settings.DEBUG else "production",
        database_connected=db_connected,
        ai_integration=ai_status,
        total_configs=total_configs
    )


@router.get("/config/", response_model=List[ConfigResponse])
async def list_configurations(
    category: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Lista todas las configuraciones del sistema.
    Los valores cifrados se muestran enmascarados.
    """
    query = db.query(SystemConfig)

    if category:
        try:
            cat = ConfigCategory(category)
            query = query.filter(SystemConfig.category == cat)
        except ValueError:
            pass

    configs = query.all()

    # Agregar configuraciones predefinidas que no existen en BD
    existing_keys = {c.config_key for c in configs}
    for key, definition in SYSTEM_CONFIG_DEFINITIONS.items():
        if key not in existing_keys:
            configs.append(SystemConfig(
                config_key=key,
                config_value=None,
                category=definition["category"],
                description=definition["description"],
                is_encrypted=definition["is_encrypted"],
                is_active=True
            ))

    # Enmascarar valores sensibles
    result = []
    for config in configs:
        value = config.config_value
        if config.is_encrypted and value:
            value = mask_api_key(value)

        result.append(ConfigResponse(
            key=config.config_key,
            value=value,
            category=config.category.value if hasattr(config.category, 'value') else str(config.category),
            description=config.description,
            is_encrypted=config.is_encrypted,
            is_active=config.is_active,
            updated_at=config.updated_at if hasattr(config, 'updated_at') else None
        ))

    return result


@router.get("/config/{config_key}", response_model=ConfigResponse)
async def get_configuration(
    config_key: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Obtiene una configuracion especifica."""
    config = db.query(SystemConfig).filter(
        SystemConfig.config_key == config_key
    ).first()

    if not config:
        # Verificar si es una configuracion predefinida
        if config_key in SYSTEM_CONFIG_DEFINITIONS:
            definition = SYSTEM_CONFIG_DEFINITIONS[config_key]
            return ConfigResponse(
                key=config_key,
                value=None,
                category=definition["category"].value,
                description=definition["description"],
                is_encrypted=definition["is_encrypted"],
                is_active=True,
                updated_at=None
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuracion no encontrada"
        )

    value = config.config_value
    if config.is_encrypted and value:
        value = mask_api_key(value)

    return ConfigResponse(
        key=config.config_key,
        value=value,
        category=config.category.value,
        description=config.description,
        is_encrypted=config.is_encrypted,
        is_active=config.is_active,
        updated_at=config.updated_at
    )


@router.put("/config/{config_key}")
async def update_configuration(
    config_key: str,
    data: ConfigValueUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Actualiza el valor de una configuracion.
    Para API keys, valida antes de guardar.
    """
    # Buscar o crear configuracion
    config = db.query(SystemConfig).filter(
        SystemConfig.config_key == config_key
    ).first()

    if not config:
        # Verificar si es una configuracion predefinida
        if config_key not in SYSTEM_CONFIG_DEFINITIONS:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Configuracion no encontrada"
            )

        definition = SYSTEM_CONFIG_DEFINITIONS[config_key]
        config = SystemConfig(
            config_key=config_key,
            category=definition["category"],
            description=definition["description"],
            is_encrypted=definition["is_encrypted"]
        )
        db.add(config)

    # Validar API key de Anthropic si aplica (a menos que se omita validacion)
    validation_result = None
    if config_key == "anthropic_api_key" and data.value:
        if not data.skip_validation:
            is_valid, error = validate_anthropic_key(data.value)
            validation_result = {
                "valid": is_valid,
                "error": error
            }
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"API key invalida: {error}"
                )
        else:
            validation_result = {
                "valid": None,
                "error": None,
                "skipped": True
            }

    # Actualizar valor
    config.config_value = data.value
    config.updated_at = datetime.utcnow()
    config.updated_by = current_user.id
    config.is_active = True

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.CONFIG_CHANGED,
        resource_type="SystemConfig",
        resource_id=config.id,
        description=f"Configuracion actualizada: {config_key}"
    )
    db.add(audit)

    db.commit()
    db.refresh(config)

    return {
        "success": True,
        "message": f"Configuracion '{config_key}' actualizada correctamente",
        "validation": validation_result
    }


@router.post("/config/anthropic/validate")
async def validate_anthropic_api_key(
    data: ConfigValueUpdate,
    current_user: User = Depends(require_admin)
) -> Dict[str, Any]:
    """
    Valida una API key de Anthropic sin guardarla.
    Util para verificar antes de guardar.
    """
    is_valid, error = validate_anthropic_key(data.value)

    return {
        "valid": is_valid,
        "error": error,
        "message": "API key valida" if is_valid else f"API key invalida: {error}"
    }


@router.delete("/config/{config_key}")
async def delete_configuration(
    config_key: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Elimina (desactiva) una configuracion."""
    config = db.query(SystemConfig).filter(
        SystemConfig.config_key == config_key
    ).first()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuracion no encontrada"
        )

    # Desactivar en lugar de eliminar
    config.is_active = False
    config.config_value = None
    config.updated_at = datetime.utcnow()
    config.updated_by = current_user.id

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.CONFIG_CHANGED,
        resource_type="SystemConfig",
        resource_id=config.id,
        description=f"Configuracion eliminada: {config_key}"
    )
    db.add(audit)

    db.commit()

    return {
        "success": True,
        "message": f"Configuracion '{config_key}' eliminada"
    }


# === Helper Functions ===
def get_config_value(db: Session, config_key: str) -> Optional[str]:
    """Obtiene el valor de una configuracion de la BD."""
    config = db.query(SystemConfig).filter(
        SystemConfig.config_key == config_key,
        SystemConfig.is_active == True
    ).first()
    return config.config_value if config else None
