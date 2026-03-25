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


def set_config_value(db: Session, config_key: str, value: str, user_id: UUID) -> None:
    """Actualiza o crea un valor de configuracion."""
    config = db.query(SystemConfig).filter(
        SystemConfig.config_key == config_key
    ).first()

    if not config:
        if config_key in SYSTEM_CONFIG_DEFINITIONS:
            definition = SYSTEM_CONFIG_DEFINITIONS[config_key]
            config = SystemConfig(
                config_key=config_key,
                category=definition["category"],
                description=definition["description"],
                is_encrypted=definition["is_encrypted"]
            )
            db.add(config)

    if config:
        config.config_value = value
        config.updated_at = datetime.utcnow()
        config.updated_by = user_id
        config.is_active = True


# === Blockchain Config Schemas ===
class BlockchainConfigSchema(BaseModel):
    """Configuracion de blockchain."""
    walletConnectProjectId: str = ""
    investmentContract: str = ""
    kycContract: str = ""
    dividendsContract: str = ""
    tokenFactoryContract: str = ""
    rpcUrls: Dict[str, str] = {}
    explorerApiKeys: Dict[str, str] = {}
    defaultNetwork: str = "polygon"
    isTestnet: bool = False


class SystemConfigSchema(BaseModel):
    """Configuracion del sistema."""
    appName: str = "FinCore"
    appVersion: str = "1.0.0"
    debugMode: bool = False
    apiUrl: str = ""
    apiTimeout: int = 30000
    maxUploadSize: int = 10
    sessionTimeout: int = 480
    kycRequired: bool = True
    minInvestment: int = 1000
    maxInvestment: int = 1000000


class FullConfigSchema(BaseModel):
    """Configuracion completa del sistema."""
    blockchain: BlockchainConfigSchema
    system: SystemConfigSchema


class FullConfigResponse(BaseModel):
    """Respuesta con configuracion completa."""
    blockchain: BlockchainConfigSchema
    system: SystemConfigSchema
    updated_at: Optional[str] = None


# === Endpoints de Configuracion Completa ===
@router.get("/config/system", response_model=FullConfigResponse)
async def get_full_config(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> FullConfigResponse:
    """
    Obtiene la configuracion completa de blockchain y sistema.
    """
    # Obtener todas las configuraciones de blockchain
    blockchain_config = BlockchainConfigSchema(
        walletConnectProjectId=get_config_value(db, "blockchain_walletconnect_project_id") or "",
        investmentContract=get_config_value(db, "blockchain_investment_contract") or "",
        kycContract=get_config_value(db, "blockchain_kyc_contract") or "",
        dividendsContract=get_config_value(db, "blockchain_dividends_contract") or "",
        tokenFactoryContract=get_config_value(db, "blockchain_token_factory_contract") or "",
        rpcUrls={
            "polygon": get_config_value(db, "blockchain_rpc_polygon") or "https://polygon-rpc.com",
            "ethereum": get_config_value(db, "blockchain_rpc_ethereum") or "https://eth.llamarpc.com",
            "arbitrum": get_config_value(db, "blockchain_rpc_arbitrum") or "https://arb1.arbitrum.io/rpc",
            "base": get_config_value(db, "blockchain_rpc_base") or "https://mainnet.base.org",
            "polygonAmoy": get_config_value(db, "blockchain_rpc_polygon_amoy") or "https://rpc-amoy.polygon.technology",
            "sepolia": get_config_value(db, "blockchain_rpc_sepolia") or "https://rpc.sepolia.org",
        },
        explorerApiKeys={
            "polygonscan": get_config_value(db, "blockchain_api_polygonscan") or "",
            "etherscan": get_config_value(db, "blockchain_api_etherscan") or "",
            "arbiscan": get_config_value(db, "blockchain_api_arbiscan") or "",
            "basescan": get_config_value(db, "blockchain_api_basescan") or "",
        },
        defaultNetwork=get_config_value(db, "blockchain_default_network") or "polygon",
        isTestnet=get_config_value(db, "blockchain_is_testnet") == "true"
    )

    # Obtener todas las configuraciones del sistema
    system_config = SystemConfigSchema(
        appName=get_config_value(db, "system_app_name") or "FinCore",
        appVersion=get_config_value(db, "system_app_version") or "1.0.0",
        debugMode=get_config_value(db, "system_debug_mode") == "true",
        apiUrl=get_config_value(db, "system_api_url") or "",
        apiTimeout=int(get_config_value(db, "system_api_timeout") or "30000"),
        maxUploadSize=int(get_config_value(db, "system_max_upload_size") or "10"),
        sessionTimeout=int(get_config_value(db, "system_session_timeout") or "480"),
        kycRequired=get_config_value(db, "system_kyc_required") != "false",
        minInvestment=int(get_config_value(db, "system_min_investment") or "1000"),
        maxInvestment=int(get_config_value(db, "system_max_investment") or "1000000")
    )

    # Obtener ultima actualizacion
    last_updated = db.query(SystemConfig.updated_at).order_by(
        SystemConfig.updated_at.desc()
    ).first()

    return FullConfigResponse(
        blockchain=blockchain_config,
        system=system_config,
        updated_at=last_updated[0].isoformat() if last_updated and last_updated[0] else None
    )


@router.put("/config/system")
async def update_full_config(
    data: FullConfigSchema,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Actualiza la configuracion completa de blockchain y sistema.
    """
    try:
        # Actualizar configuracion de blockchain
        set_config_value(db, "blockchain_walletconnect_project_id", data.blockchain.walletConnectProjectId, current_user.id)
        set_config_value(db, "blockchain_investment_contract", data.blockchain.investmentContract, current_user.id)
        set_config_value(db, "blockchain_kyc_contract", data.blockchain.kycContract, current_user.id)
        set_config_value(db, "blockchain_dividends_contract", data.blockchain.dividendsContract, current_user.id)
        set_config_value(db, "blockchain_token_factory_contract", data.blockchain.tokenFactoryContract, current_user.id)
        set_config_value(db, "blockchain_default_network", data.blockchain.defaultNetwork, current_user.id)
        set_config_value(db, "blockchain_is_testnet", str(data.blockchain.isTestnet).lower(), current_user.id)

        # RPC URLs
        if data.blockchain.rpcUrls:
            set_config_value(db, "blockchain_rpc_polygon", data.blockchain.rpcUrls.get("polygon", ""), current_user.id)
            set_config_value(db, "blockchain_rpc_ethereum", data.blockchain.rpcUrls.get("ethereum", ""), current_user.id)
            set_config_value(db, "blockchain_rpc_arbitrum", data.blockchain.rpcUrls.get("arbitrum", ""), current_user.id)
            set_config_value(db, "blockchain_rpc_base", data.blockchain.rpcUrls.get("base", ""), current_user.id)
            set_config_value(db, "blockchain_rpc_polygon_amoy", data.blockchain.rpcUrls.get("polygonAmoy", ""), current_user.id)
            set_config_value(db, "blockchain_rpc_sepolia", data.blockchain.rpcUrls.get("sepolia", ""), current_user.id)

        # Explorer API Keys
        if data.blockchain.explorerApiKeys:
            set_config_value(db, "blockchain_api_polygonscan", data.blockchain.explorerApiKeys.get("polygonscan", ""), current_user.id)
            set_config_value(db, "blockchain_api_etherscan", data.blockchain.explorerApiKeys.get("etherscan", ""), current_user.id)
            set_config_value(db, "blockchain_api_arbiscan", data.blockchain.explorerApiKeys.get("arbiscan", ""), current_user.id)
            set_config_value(db, "blockchain_api_basescan", data.blockchain.explorerApiKeys.get("basescan", ""), current_user.id)

        # Actualizar configuracion del sistema
        set_config_value(db, "system_app_name", data.system.appName, current_user.id)
        set_config_value(db, "system_app_version", data.system.appVersion, current_user.id)
        set_config_value(db, "system_debug_mode", str(data.system.debugMode).lower(), current_user.id)
        set_config_value(db, "system_api_timeout", str(data.system.apiTimeout), current_user.id)
        set_config_value(db, "system_max_upload_size", str(data.system.maxUploadSize), current_user.id)
        set_config_value(db, "system_session_timeout", str(data.system.sessionTimeout), current_user.id)
        set_config_value(db, "system_kyc_required", str(data.system.kycRequired).lower(), current_user.id)
        set_config_value(db, "system_min_investment", str(data.system.minInvestment), current_user.id)
        set_config_value(db, "system_max_investment", str(data.system.maxInvestment), current_user.id)

        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            action=AuditAction.CONFIG_CHANGED,
            resource_type="SystemConfig",
            description="Configuracion de sistema actualizada (blockchain y sistema)"
        )
        db.add(audit)

        db.commit()

        return {
            "success": True,
            "message": "Configuracion actualizada correctamente",
            "updated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando configuracion: {str(e)}"
        )
