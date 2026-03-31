"""
Endpoints para gestión de API Keys.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.api_keys import APIKey, APIKeyLog, APIKeyStatus
from app.models.audit import AuditLog, AuditAction
from app.schemas.api_keys import (
    APIKeyCreate, APIKeyResponse, APIKeyCreatedResponse, APIKeyUpdate,
    APIKeyLogEntry, APIKeyLogsResponse, APIKeyStatsResponse
)

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.get("", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Listar todas las API Keys del usuario."""
    keys = db.query(APIKey).filter(
        APIKey.user_id == current_user.id
    ).order_by(desc(APIKey.created_at)).all()

    return [
        APIKeyResponse(
            id=key.id,
            name=key.name,
            description=key.description,
            key_prefix=key.key_prefix,
            permissions=key.permissions or [],
            allowed_ips=key.allowed_ips,
            status=key.status.value,
            expires_at=key.expires_at,
            rate_limit_per_minute=key.rate_limit_per_minute,
            rate_limit_per_day=key.rate_limit_per_day,
            last_used_at=key.last_used_at,
            last_used_ip=key.last_used_ip,
            total_requests=key.total_requests,
            created_at=key.created_at
        )
        for key in keys
    ]


@router.post("", response_model=APIKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crear una nueva API Key.

    **IMPORTANTE**: La API Key completa solo se muestra UNA VEZ.
    Guárdala de forma segura.
    """
    # Límite de API Keys por usuario
    existing_count = db.query(func.count(APIKey.id)).filter(
        APIKey.user_id == current_user.id,
        APIKey.status == APIKeyStatus.ACTIVE
    ).scalar()

    if existing_count >= 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Límite de 10 API Keys activas alcanzado"
        )

    # Generar key
    full_key, prefix, key_hash = APIKey.generate_key()

    # Crear API Key
    api_key = APIKey(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        key_prefix=prefix,
        key_hash=key_hash,
        permissions=data.permissions,
        allowed_ips=data.allowed_ips,
        expires_at=data.expires_at,
        rate_limit_per_minute=data.rate_limit_per_minute,
        rate_limit_per_day=data.rate_limit_per_day,
    )

    db.add(api_key)

    # Audit log
    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditAction.CREATE.value if hasattr(AuditAction, 'CREATE') else "create",
        resource_type="api_key",
        resource_id=str(api_key.id),
        description=f"API Key creada: {data.name}",
    ))

    db.commit()
    db.refresh(api_key)

    return APIKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key=full_key,  # Solo se muestra esta única vez
        key_prefix=prefix,
        permissions=api_key.permissions or [],
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener detalle de una API Key."""
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key no encontrada"
        )

    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        description=api_key.description,
        key_prefix=api_key.key_prefix,
        permissions=api_key.permissions or [],
        allowed_ips=api_key.allowed_ips,
        status=api_key.status.value,
        expires_at=api_key.expires_at,
        rate_limit_per_minute=api_key.rate_limit_per_minute,
        rate_limit_per_day=api_key.rate_limit_per_day,
        last_used_at=api_key.last_used_at,
        last_used_ip=api_key.last_used_ip,
        total_requests=api_key.total_requests,
        created_at=api_key.created_at
    )


@router.put("/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: UUID,
    data: APIKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Actualizar una API Key."""
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id,
        APIKey.status == APIKeyStatus.ACTIVE
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key no encontrada o revocada"
        )

    # Actualizar campos
    if data.name is not None:
        api_key.name = data.name
    if data.description is not None:
        api_key.description = data.description
    if data.permissions is not None:
        api_key.permissions = data.permissions
    if data.allowed_ips is not None:
        api_key.allowed_ips = data.allowed_ips
    if data.rate_limit_per_minute is not None:
        api_key.rate_limit_per_minute = data.rate_limit_per_minute
    if data.rate_limit_per_day is not None:
        api_key.rate_limit_per_day = data.rate_limit_per_day

    db.commit()
    db.refresh(api_key)

    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        description=api_key.description,
        key_prefix=api_key.key_prefix,
        permissions=api_key.permissions or [],
        allowed_ips=api_key.allowed_ips,
        status=api_key.status.value,
        expires_at=api_key.expires_at,
        rate_limit_per_minute=api_key.rate_limit_per_minute,
        rate_limit_per_day=api_key.rate_limit_per_day,
        last_used_at=api_key.last_used_at,
        last_used_ip=api_key.last_used_ip,
        total_requests=api_key.total_requests,
        created_at=api_key.created_at
    )


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revocar (desactivar) una API Key."""
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key no encontrada"
        )

    if api_key.status == APIKeyStatus.REVOKED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API Key ya está revocada"
        )

    api_key.status = APIKeyStatus.REVOKED
    api_key.revoked_at = datetime.utcnow()

    # Audit log
    db.add(AuditLog(
        user_id=current_user.id,
        action=AuditAction.DELETE.value if hasattr(AuditAction, 'DELETE') else "delete",
        resource_type="api_key",
        resource_id=str(api_key.id),
        description=f"API Key revocada: {api_key.name}",
    ))

    db.commit()

    return {"message": "API Key revocada exitosamente", "key_id": str(key_id)}


@router.get("/{key_id}/logs", response_model=APIKeyLogsResponse)
async def get_api_key_logs(
    key_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener logs de uso de una API Key."""
    # Verificar pertenencia
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key no encontrada"
        )

    # Obtener logs
    logs = db.query(APIKeyLog).filter(
        APIKeyLog.api_key_id == key_id
    ).order_by(desc(APIKeyLog.created_at)).offset(offset).limit(limit).all()

    total = db.query(func.count(APIKeyLog.id)).filter(
        APIKeyLog.api_key_id == key_id
    ).scalar()

    return APIKeyLogsResponse(
        logs=[
            APIKeyLogEntry(
                id=log.id,
                endpoint=log.endpoint,
                method=log.method,
                ip_address=log.ip_address,
                status_code=log.status_code,
                response_time_ms=log.response_time_ms,
                error_message=log.error_message,
                created_at=log.created_at
            )
            for log in logs
        ],
        total=total or 0,
        page=offset // limit + 1 if limit > 0 else 1,
        page_size=limit
    )


@router.get("/{key_id}/stats", response_model=APIKeyStatsResponse)
async def get_api_key_stats(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener estadísticas de uso de una API Key."""
    # Verificar pertenencia
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key no encontrada"
        )

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Requests hoy
    requests_today = db.query(func.count(APIKeyLog.id)).filter(
        APIKeyLog.api_key_id == key_id,
        APIKeyLog.created_at >= today_start
    ).scalar() or 0

    # Requests este mes
    requests_this_month = db.query(func.count(APIKeyLog.id)).filter(
        APIKeyLog.api_key_id == key_id,
        APIKeyLog.created_at >= month_start
    ).scalar() or 0

    # Tiempo de respuesta promedio
    avg_response = db.query(func.avg(APIKeyLog.response_time_ms)).filter(
        APIKeyLog.api_key_id == key_id,
        APIKeyLog.response_time_ms.isnot(None)
    ).scalar() or 0

    # Tasa de error
    total_requests = api_key.total_requests or 1
    error_count = db.query(func.count(APIKeyLog.id)).filter(
        APIKeyLog.api_key_id == key_id,
        APIKeyLog.status_code >= 400
    ).scalar() or 0
    error_rate = (error_count / total_requests) * 100 if total_requests > 0 else 0

    # Top endpoints
    top_endpoints_raw = db.query(
        APIKeyLog.endpoint,
        func.count(APIKeyLog.id).label('count')
    ).filter(
        APIKeyLog.api_key_id == key_id
    ).group_by(APIKeyLog.endpoint).order_by(
        desc('count')
    ).limit(5).all()

    top_endpoints = [
        {"endpoint": e.endpoint, "count": e.count}
        for e in top_endpoints_raw
    ]

    # Requests por día (últimos 7 días)
    requests_by_day = []
    for i in range(7):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = db.query(func.count(APIKeyLog.id)).filter(
            APIKeyLog.api_key_id == key_id,
            APIKeyLog.created_at >= day_start,
            APIKeyLog.created_at < day_end
        ).scalar() or 0
        requests_by_day.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "count": count
        })

    return APIKeyStatsResponse(
        api_key_id=api_key.id,
        total_requests=api_key.total_requests or 0,
        requests_today=requests_today,
        requests_this_month=requests_this_month,
        avg_response_time_ms=float(avg_response),
        error_rate=float(error_rate),
        top_endpoints=top_endpoints,
        requests_by_day=list(reversed(requests_by_day))
    )


@router.get("/permissions/available")
async def get_available_permissions(
    current_user: User = Depends(get_current_user),
):
    """Obtener lista de permisos disponibles."""
    return {
        "permissions": [
            {"code": "read:portfolio", "name": "Leer Portfolio", "category": "Lectura"},
            {"code": "read:transactions", "name": "Leer Transacciones", "category": "Lectura"},
            {"code": "read:balances", "name": "Leer Balances", "category": "Lectura"},
            {"code": "read:market", "name": "Leer Datos de Mercado", "category": "Lectura"},
            {"code": "trade:spot", "name": "Trading Spot", "category": "Trading"},
            {"code": "trade:create_order", "name": "Crear Órdenes", "category": "Trading"},
            {"code": "trade:cancel_order", "name": "Cancelar Órdenes", "category": "Trading"},
            {"code": "wallet:deposit", "name": "Ver Depósitos", "category": "Wallet"},
            {"code": "wallet:withdraw", "name": "Realizar Retiros", "category": "Wallet"},
            {"code": "wallet:transfer", "name": "Transferencias", "category": "Wallet"},
            {"code": "remittance:create", "name": "Crear Remesas", "category": "Remesas"},
            {"code": "remittance:read", "name": "Leer Remesas", "category": "Remesas"},
        ]
    }
