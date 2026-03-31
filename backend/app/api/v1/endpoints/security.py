"""
Endpoints de Seguridad Avanzada.

Implementa:
- Whitelist de direcciones de retiro con cuarentena 24h
- Sistema anti-phishing
- Backup codes MFA
- Gestión de dispositivos y sesiones
- Congelamiento de cuenta
- Verificación HIBP
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.config import settings
from app.core.security import (
    get_current_user, verify_password, hash_password,
    encrypt_data, decrypt_data, check_password_hibp
)
from app.models.user import User
from app.models.audit import AuditLog, AuditAction
from app.models.security import (
    WithdrawalWhitelist, UserDevice, UserSession, PasswordHistory,
    AccountFreeze, AntiPhishingPhrase, MFABackupCode,
    WithdrawalAddressType, WhitelistStatus, DeviceStatus, AccountFreezeReason
)
from app.schemas.security import (
    WithdrawalAddressCreate, WithdrawalAddressResponse, WhitelistListResponse,
    CancelWhitelistRequest, AntiPhishingSetup, AntiPhishingResponse,
    MFABackupCodesResponse, MFABackupCodesStatus, MFABackupCodeVerify,
    DeviceResponse, DeviceListResponse, DeviceUpdate,
    SessionResponse, SessionListResponse, RevokeSessionRequest,
    FreezeAccountRequest, FreezeAccountResponse, UnfreezeAccountRequest,
    PasswordChangeRequest, PasswordStrengthResponse,
    SecurityActivityResponse, SecurityActivityListResponse,
    SecuritySummaryResponse
)
from app.services.email_service import email_service
from app.services.device_service import DeviceService, get_device_service

router = APIRouter(prefix="/security", tags=["Seguridad"])

# Constantes
QUARANTINE_HOURS = 24
PASSWORD_HISTORY_LIMIT = 10
BACKUP_CODES_COUNT = 8


# ============ Whitelist de Retiros ============

@router.post("/whitelist", response_model=WithdrawalAddressResponse, status_code=status.HTTP_201_CREATED)
async def add_withdrawal_address(
    request: Request,
    data: WithdrawalAddressCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Agregar nueva dirección de retiro a la whitelist.

    La dirección entrará en cuarentena por 24 horas antes de poder usarse.
    Se enviarán notificaciones por email, push y SMS.
    """
    # Verificar que la cuenta no esté congelada
    active_freeze = db.query(AccountFreeze).filter(
        AccountFreeze.user_id == current_user.id,
        AccountFreeze.is_active == True
    ).first()

    if active_freeze:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta está congelada. Descongélala para agregar direcciones."
        )

    # Crear hash de la dirección para búsqueda
    address_hash = hashlib.sha256(data.address.lower().encode()).hexdigest()

    # Verificar si ya existe
    existing = db.query(WithdrawalWhitelist).filter(
        WithdrawalWhitelist.user_id == current_user.id,
        WithdrawalWhitelist.address_hash == address_hash,
        WithdrawalWhitelist.status.in_([WhitelistStatus.PENDING, WhitelistStatus.ACTIVE])
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta dirección ya está en tu whitelist"
        )

    # Calcular fin de cuarentena
    quarantine_ends = datetime.utcnow() + timedelta(hours=QUARANTINE_HOURS)

    # Generar token de cancelación
    cancellation_token = WithdrawalWhitelist.generate_cancellation_token()

    # Crear entrada en whitelist
    whitelist_entry = WithdrawalWhitelist(
        user_id=current_user.id,
        address_type=WithdrawalAddressType(data.address_type),
        address=data.address,
        address_hash=address_hash,
        label=data.label,
        metadata=data.metadata or {},
        status=WhitelistStatus.PENDING,
        quarantine_ends_at=quarantine_ends,
        cancellation_token=cancellation_token,
        cancellation_token_expires=quarantine_ends,
        added_from_ip=request.client.host if request.client else None
    )

    db.add(whitelist_entry)

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.WHITELIST_ADDRESS_ADDED,
        resource_type="WithdrawalWhitelist",
        ip_address=request.client.host if request.client else None,
        description=f"Nueva dirección agregada a whitelist: {_mask_address(data.address, data.address_type)}"
    )
    db.add(audit)
    db.commit()
    db.refresh(whitelist_entry)

    # Enviar notificaciones en background
    background_tasks.add_task(
        _send_whitelist_notifications,
        user=current_user,
        address=data.address,
        address_type=data.address_type,
        quarantine_ends=quarantine_ends,
        cancellation_token=cancellation_token
    )

    # Marcar notificaciones como enviadas
    whitelist_entry.notification_email_sent = True
    db.commit()

    return WithdrawalAddressResponse(
        id=whitelist_entry.id,
        address_type=whitelist_entry.address_type.value,
        address=whitelist_entry.address,
        address_masked=_mask_address(whitelist_entry.address, whitelist_entry.address_type.value),
        label=whitelist_entry.label,
        status=whitelist_entry.status.value,
        is_in_quarantine=whitelist_entry.is_in_quarantine,
        quarantine_ends_at=whitelist_entry.quarantine_ends_at,
        can_be_used=whitelist_entry.can_be_used,
        is_primary=whitelist_entry.is_primary,
        times_used=whitelist_entry.times_used,
        last_used_at=whitelist_entry.last_used_at,
        created_at=whitelist_entry.created_at,
        activated_at=whitelist_entry.activated_at
    )


@router.get("/whitelist", response_model=WhitelistListResponse)
async def list_whitelist_addresses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    include_cancelled: bool = False
):
    """Listar todas las direcciones en whitelist del usuario."""
    query = db.query(WithdrawalWhitelist).filter(
        WithdrawalWhitelist.user_id == current_user.id
    )

    if not include_cancelled:
        query = query.filter(
            WithdrawalWhitelist.status.in_([WhitelistStatus.PENDING, WhitelistStatus.ACTIVE])
        )

    addresses = query.order_by(WithdrawalWhitelist.created_at.desc()).all()

    # Actualizar estado de las que terminaron cuarentena
    for addr in addresses:
        if addr.status == WhitelistStatus.PENDING and not addr.is_in_quarantine:
            addr.status = WhitelistStatus.ACTIVE
            addr.activated_at = datetime.utcnow()

    db.commit()

    return WhitelistListResponse(
        addresses=[
            WithdrawalAddressResponse(
                id=addr.id,
                address_type=addr.address_type.value,
                address=addr.address,
                address_masked=_mask_address(addr.address, addr.address_type.value),
                label=addr.label,
                status=addr.status.value,
                is_in_quarantine=addr.is_in_quarantine,
                quarantine_ends_at=addr.quarantine_ends_at,
                can_be_used=addr.can_be_used,
                is_primary=addr.is_primary,
                times_used=addr.times_used,
                last_used_at=addr.last_used_at,
                created_at=addr.created_at,
                activated_at=addr.activated_at
            )
            for addr in addresses
        ],
        total=len(addresses)
    )


@router.delete("/whitelist/{address_id}")
async def remove_whitelist_address(
    address_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar dirección de whitelist."""
    address = db.query(WithdrawalWhitelist).filter(
        WithdrawalWhitelist.id == address_id,
        WithdrawalWhitelist.user_id == current_user.id
    ).first()

    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dirección no encontrada"
        )

    address.status = WhitelistStatus.CANCELLED
    address.cancelled_at = datetime.utcnow()

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.WHITELIST_ADDRESS_REMOVED,
        resource_type="WithdrawalWhitelist",
        resource_id=address_id,
        ip_address=request.client.host if request.client else None,
        description=f"Dirección eliminada de whitelist: {_mask_address(address.address, address.address_type.value)}"
    )
    db.add(audit)
    db.commit()

    return {"message": "Dirección eliminada de la whitelist"}


@router.post("/whitelist/cancel")
async def cancel_whitelist_by_token(
    data: CancelWhitelistRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Cancelar dirección en cuarentena usando el token del email.

    Este endpoint no requiere autenticación - el token es la verificación.
    """
    address = db.query(WithdrawalWhitelist).filter(
        WithdrawalWhitelist.cancellation_token == data.cancellation_token,
        WithdrawalWhitelist.status == WhitelistStatus.PENDING
    ).first()

    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token inválido o dirección ya procesada"
        )

    if address.cancellation_token_expires < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token de cancelación ha expirado"
        )

    address.status = WhitelistStatus.CANCELLED
    address.cancelled_at = datetime.utcnow()
    address.cancellation_token = None

    # Audit log
    audit = AuditLog(
        user_id=address.user_id,
        action=AuditAction.WHITELIST_ADDRESS_REMOVED,
        resource_type="WithdrawalWhitelist",
        resource_id=address.id,
        ip_address=request.client.host if request.client else None,
        description="Dirección cancelada via link de email durante cuarentena"
    )
    db.add(audit)
    db.commit()

    return {"message": "Dirección cancelada exitosamente"}


@router.put("/whitelist/{address_id}/primary")
async def set_primary_address(
    address_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Marcar una dirección como principal."""
    address = db.query(WithdrawalWhitelist).filter(
        WithdrawalWhitelist.id == address_id,
        WithdrawalWhitelist.user_id == current_user.id,
        WithdrawalWhitelist.status == WhitelistStatus.ACTIVE
    ).first()

    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dirección no encontrada o no activa"
        )

    # Quitar primary de otras del mismo tipo
    db.query(WithdrawalWhitelist).filter(
        WithdrawalWhitelist.user_id == current_user.id,
        WithdrawalWhitelist.address_type == address.address_type,
        WithdrawalWhitelist.id != address_id
    ).update({"is_primary": False})

    address.is_primary = True
    db.commit()

    return {"message": "Dirección marcada como principal"}


# ============ Anti-Phishing ============

@router.post("/anti-phishing", response_model=AntiPhishingResponse)
async def setup_anti_phishing(
    data: AntiPhishingSetup,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Configurar frase anti-phishing."""
    # Cifrar la frase
    encrypted_phrase = encrypt_data(data.phrase)

    # Verificar si ya existe
    existing = db.query(AntiPhishingPhrase).filter(
        AntiPhishingPhrase.user_id == current_user.id
    ).first()

    if existing:
        existing.phrase_encrypted = encrypted_phrase
        existing.phrase_hint = data.phrase_hint
    else:
        anti_phishing = AntiPhishingPhrase(
            user_id=current_user.id,
            phrase_encrypted=encrypted_phrase,
            phrase_hint=data.phrase_hint
        )
        db.add(anti_phishing)

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.ANTI_PHISHING_CONFIGURED,
        ip_address=request.client.host if request.client else None,
        description="Frase anti-phishing configurada/actualizada"
    )
    db.add(audit)
    db.commit()

    return AntiPhishingResponse(
        is_configured=True,
        phrase_hint=data.phrase_hint,
        created_at=existing.created_at if existing else datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@router.get("/anti-phishing", response_model=AntiPhishingResponse)
async def get_anti_phishing_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener estado de frase anti-phishing."""
    anti_phishing = db.query(AntiPhishingPhrase).filter(
        AntiPhishingPhrase.user_id == current_user.id
    ).first()

    return AntiPhishingResponse(
        is_configured=anti_phishing is not None,
        phrase_hint=anti_phishing.phrase_hint if anti_phishing else None,
        created_at=anti_phishing.created_at if anti_phishing else None,
        updated_at=anti_phishing.updated_at if anti_phishing else None
    )


# ============ Backup Codes MFA ============

@router.post("/mfa/backup-codes", response_model=MFABackupCodesResponse)
async def generate_backup_codes(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generar nuevos códigos de respaldo MFA.

    ADVERTENCIA: Esto invalida todos los códigos anteriores.
    Los códigos solo se muestran una vez.
    """
    if not current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA no está habilitado. Habilítalo primero."
        )

    # Eliminar códigos anteriores
    db.query(MFABackupCode).filter(
        MFABackupCode.user_id == current_user.id
    ).delete()

    # Generar nuevos códigos
    codes = MFABackupCode.generate_codes(BACKUP_CODES_COUNT)

    for code in codes:
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        backup_code = MFABackupCode(
            user_id=current_user.id,
            code_hash=code_hash
        )
        db.add(backup_code)

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.MFA_BACKUP_CODES_GENERATED,
        ip_address=request.client.host if request.client else None,
        description="Códigos de respaldo MFA generados"
    )
    db.add(audit)
    db.commit()

    return MFABackupCodesResponse(
        codes=codes,
        generated_at=datetime.utcnow()
    )


@router.get("/mfa/backup-codes/status", response_model=MFABackupCodesStatus)
async def get_backup_codes_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener estado de códigos de respaldo."""
    codes = db.query(MFABackupCode).filter(
        MFABackupCode.user_id == current_user.id
    ).all()

    total = len(codes)
    used = sum(1 for c in codes if c.is_used)
    last_used = max((c.used_at for c in codes if c.used_at), default=None)

    return MFABackupCodesStatus(
        total_codes=total,
        used_codes=used,
        remaining_codes=total - used,
        last_used_at=last_used
    )


@router.post("/mfa/backup-codes/verify")
async def verify_backup_code(
    data: MFABackupCodeVerify,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Verificar y consumir un código de respaldo."""
    code_hash = hashlib.sha256(data.code.encode()).hexdigest()

    backup_code = db.query(MFABackupCode).filter(
        MFABackupCode.user_id == current_user.id,
        MFABackupCode.code_hash == code_hash,
        MFABackupCode.is_used == False
    ).first()

    if not backup_code:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código inválido o ya utilizado"
        )

    # Marcar como usado
    backup_code.is_used = True
    backup_code.used_at = datetime.utcnow()
    backup_code.used_from_ip = request.client.host if request.client else None

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.MFA_BACKUP_CODE_USED,
        ip_address=request.client.host if request.client else None,
        description="Código de respaldo MFA utilizado"
    )
    db.add(audit)
    db.commit()

    return {"message": "Código verificado correctamente", "valid": True}


# ============ Congelamiento de Cuenta ============

@router.post("/freeze", response_model=FreezeAccountResponse)
async def freeze_account(
    data: FreezeAccountRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Congelar cuenta temporalmente.

    Bloquea todas las operaciones financieras.
    Para descongelar se requiere verificación por email.
    """
    # Verificar si ya está congelada
    existing = db.query(AccountFreeze).filter(
        AccountFreeze.user_id == current_user.id,
        AccountFreeze.is_active == True
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tu cuenta ya está congelada"
        )

    # Generar token de descongelamiento
    unfreeze_token = AccountFreeze.generate_unfreeze_token()

    freeze = AccountFreeze(
        user_id=current_user.id,
        reason=AccountFreezeReason.USER_REQUESTED,
        reason_details=data.reason,
        unfreeze_token=unfreeze_token,
        unfreeze_token_expires=datetime.utcnow() + timedelta(days=30),
        frozen_from_ip=request.client.host if request.client else None
    )
    db.add(freeze)

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.ACCOUNT_FROZEN,
        ip_address=request.client.host if request.client else None,
        description="Cuenta congelada por solicitud del usuario"
    )
    db.add(audit)
    db.commit()

    # Enviar email con instrucciones
    background_tasks.add_task(
        _send_freeze_notification,
        user=current_user,
        unfreeze_token=unfreeze_token
    )

    return FreezeAccountResponse(
        is_frozen=True,
        frozen_at=freeze.frozen_at,
        reason="Solicitado por el usuario",
        unfreeze_instructions="Te hemos enviado un email con instrucciones para descongelar tu cuenta."
    )


@router.post("/unfreeze")
async def unfreeze_account(
    data: UnfreezeAccountRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Descongelar cuenta usando el token del email.

    No requiere autenticación - el token es la verificación.
    """
    freeze = db.query(AccountFreeze).filter(
        AccountFreeze.unfreeze_token == data.unfreeze_token,
        AccountFreeze.is_active == True
    ).first()

    if not freeze:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token inválido o cuenta no congelada"
        )

    if freeze.unfreeze_token_expires < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token ha expirado. Contacta a soporte."
        )

    freeze.is_active = False
    freeze.unfrozen_at = datetime.utcnow()
    freeze.unfrozen_from_ip = request.client.host if request.client else None
    freeze.unfreeze_token = None

    # Audit log
    audit = AuditLog(
        user_id=freeze.user_id,
        action=AuditAction.ACCOUNT_UNFROZEN,
        ip_address=request.client.host if request.client else None,
        description="Cuenta descongelada via email"
    )
    db.add(audit)
    db.commit()

    return {"message": "Cuenta descongelada exitosamente"}


@router.get("/freeze/status")
async def get_freeze_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Verificar si la cuenta está congelada."""
    freeze = db.query(AccountFreeze).filter(
        AccountFreeze.user_id == current_user.id,
        AccountFreeze.is_active == True
    ).first()

    return {
        "is_frozen": freeze is not None,
        "frozen_at": freeze.frozen_at if freeze else None,
        "reason": freeze.reason.value if freeze else None
    }


# ============ Resumen de Seguridad ============

@router.get("/summary", response_model=SecuritySummaryResponse)
async def get_security_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener resumen completo del estado de seguridad."""
    recommendations = []

    # MFA
    mfa_enabled = current_user.mfa_enabled
    if not mfa_enabled:
        recommendations.append("Activa la autenticación de dos factores (2FA)")

    backup_codes = db.query(MFABackupCode).filter(
        MFABackupCode.user_id == current_user.id,
        MFABackupCode.is_used == False
    ).count()

    if mfa_enabled and backup_codes < 3:
        recommendations.append("Genera nuevos códigos de respaldo MFA")

    # Anti-phishing
    anti_phishing = db.query(AntiPhishingPhrase).filter(
        AntiPhishingPhrase.user_id == current_user.id
    ).first()

    if not anti_phishing:
        recommendations.append("Configura tu frase anti-phishing")

    # Dispositivos
    devices = db.query(UserDevice).filter(
        UserDevice.user_id == current_user.id
    ).all()
    trusted_devices = sum(1 for d in devices if d.status == DeviceStatus.TRUSTED)

    # Sesiones
    active_sessions = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active == True
    ).count()

    # Whitelist
    whitelist_query = db.query(WithdrawalWhitelist).filter(
        WithdrawalWhitelist.user_id == current_user.id
    )
    total_addresses = whitelist_query.filter(
        WithdrawalWhitelist.status.in_([WhitelistStatus.PENDING, WhitelistStatus.ACTIVE])
    ).count()
    quarantine_addresses = whitelist_query.filter(
        WithdrawalWhitelist.status == WhitelistStatus.PENDING
    ).count()

    # Cuenta congelada
    is_frozen = db.query(AccountFreeze).filter(
        AccountFreeze.user_id == current_user.id,
        AccountFreeze.is_active == True
    ).first() is not None

    # Calcular score
    score = 0
    if mfa_enabled:
        score += 30
    if backup_codes >= 3:
        score += 10
    if anti_phishing:
        score += 20
    if trusted_devices > 0:
        score += 15
    if total_addresses > 0:
        score += 15
    if current_user.email_verified:
        score += 10

    return SecuritySummaryResponse(
        mfa_enabled=mfa_enabled,
        mfa_backup_codes_remaining=backup_codes,
        anti_phishing_configured=anti_phishing is not None,
        total_devices=len(devices),
        trusted_devices=trusted_devices,
        active_sessions=active_sessions,
        whitelisted_addresses=total_addresses,
        addresses_in_quarantine=quarantine_addresses,
        is_frozen=is_frozen,
        password_last_changed=None,  # TODO: Implementar tracking
        password_expires_at=None,  # TODO: Implementar rotación
        security_score=min(score, 100),
        recommendations=recommendations
    )


# ============ Helpers ============

def _mask_address(address: str, address_type: str) -> str:
    """Enmascara una dirección para mostrar."""
    if address_type.startswith("crypto"):
        # Mostrar primeros 6 y últimos 4
        return f"{address[:6]}...{address[-4:]}"
    elif address_type == "bank_clabe":
        # Mostrar últimos 4
        return f"**************{address[-4:]}"
    else:
        # Mostrar primeros 4 y últimos 4
        if len(address) > 8:
            return f"{address[:4]}...{address[-4:]}"
        return address


async def _send_whitelist_notifications(
    user: User,
    address: str,
    address_type: str,
    quarantine_ends: datetime,
    cancellation_token: str
):
    """Envía notificaciones de nueva dirección en whitelist."""
    cancel_url = f"{settings.FRONTEND_URL}/security/whitelist/cancel?token={cancellation_token}"

    # Email
    subject = "Nueva dirección de retiro agregada - FinCore"
    html_content = f"""
    <h2>Nueva dirección de retiro</h2>
    <p>Se ha agregado una nueva dirección de retiro a tu cuenta:</p>
    <p><strong>Tipo:</strong> {address_type}</p>
    <p><strong>Dirección:</strong> {_mask_address(address, address_type)}</p>
    <p>Esta dirección estará en cuarentena hasta: <strong>{quarantine_ends.strftime('%Y-%m-%d %H:%M UTC')}</strong></p>
    <p>Si NO reconoces esta acción, cancélala inmediatamente:</p>
    <a href="{cancel_url}" style="background: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
        Cancelar dirección
    </a>
    """

    email_service._send_email(user.email, subject, html_content)


async def _send_freeze_notification(user: User, unfreeze_token: str):
    """Envía notificación de cuenta congelada."""
    unfreeze_url = f"{settings.FRONTEND_URL}/security/unfreeze?token={unfreeze_token}"

    subject = "Tu cuenta ha sido congelada - FinCore"
    html_content = f"""
    <h2>Cuenta Congelada</h2>
    <p>Tu cuenta de FinCore ha sido congelada por tu solicitud.</p>
    <p>Mientras tu cuenta esté congelada:</p>
    <ul>
        <li>No se pueden realizar retiros</li>
        <li>No se pueden agregar nuevas direcciones</li>
        <li>Las remesas están bloqueadas</li>
    </ul>
    <p>Para descongelar tu cuenta, haz clic en el siguiente enlace:</p>
    <a href="{unfreeze_url}" style="background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
        Descongelar cuenta
    </a>
    <p><small>Este enlace expira en 30 días.</small></p>
    """

    email_service._send_email(user.email, subject, html_content)


# ============ Cambio de Contraseña ============

@router.post("/password/change")
async def change_password(
    data: PasswordChangeRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cambiar contraseña del usuario.

    Validaciones:
    - Contraseña actual correcta
    - Nueva contraseña cumple requisitos (12 chars, mayús, minús, núm, símbolo)
    - No está en las últimas 10 contraseñas usadas
    - No está comprometida en HIBP
    """
    # Verificar contraseña actual
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contraseña actual incorrecta"
        )

    # Verificar que no sea igual a la actual
    if verify_password(data.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe ser diferente a la actual"
        )

    # Verificar historial de contraseñas (últimas 10)
    password_history = db.query(PasswordHistory).filter(
        PasswordHistory.user_id == current_user.id
    ).order_by(PasswordHistory.created_at.desc()).limit(PASSWORD_HISTORY_LIMIT).all()

    for old_password in password_history:
        if verify_password(data.new_password, old_password.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No puedes reutilizar las últimas {PASSWORD_HISTORY_LIMIT} contraseñas"
            )

    # Verificar en HIBP (Have I Been Pwned)
    is_compromised, breach_count = await check_password_hibp(data.new_password)
    if is_compromised:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Esta contraseña ha sido expuesta en {breach_count:,} filtraciones de datos. "
                   f"Por tu seguridad, elige una contraseña diferente."
        )

    # Guardar contraseña actual en historial
    history_entry = PasswordHistory(
        user_id=current_user.id,
        password_hash=current_user.password_hash
    )
    db.add(history_entry)

    # Actualizar contraseña
    current_user.password_hash = hash_password(data.new_password)

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.PASSWORD_CHANGED,
        ip_address=request.client.host if request.client else None,
        description="Contraseña cambiada exitosamente"
    )
    db.add(audit)
    db.commit()

    # Notificar por email
    background_tasks.add_task(
        _send_password_changed_notification,
        user=current_user
    )

    return {"message": "Contraseña actualizada exitosamente"}


@router.post("/password/check", response_model=PasswordStrengthResponse)
async def check_password_strength(
    password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verificar fortaleza de una contraseña.

    Incluye verificación HIBP para detectar contraseñas comprometidas.
    """
    import re

    issues = []
    suggestions = []
    score = 0

    # Longitud
    if len(password) >= 12:
        score += 25
    elif len(password) >= 8:
        score += 15
        issues.append("Muy corta (mínimo 12 caracteres recomendado)")
    else:
        issues.append("Muy corta (mínimo 12 caracteres)")

    # Mayúsculas
    if re.search(r"[A-Z]", password):
        score += 15
    else:
        issues.append("Sin mayúsculas")
        suggestions.append("Agrega al menos una letra mayúscula")

    # Minúsculas
    if re.search(r"[a-z]", password):
        score += 15
    else:
        issues.append("Sin minúsculas")
        suggestions.append("Agrega al menos una letra minúscula")

    # Números
    if re.search(r"\d", password):
        score += 15
    else:
        issues.append("Sin números")
        suggestions.append("Agrega al menos un número")

    # Símbolos
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        score += 20
    else:
        issues.append("Sin símbolos especiales")
        suggestions.append("Agrega símbolos como !@#$%^&*()")

    # Longitud extra
    if len(password) >= 16:
        score += 10

    # Verificar HIBP
    is_compromised, breach_count = await check_password_hibp(password)

    if is_compromised:
        score = max(0, score - 50)
        issues.insert(0, f"Comprometida en {breach_count:,} filtraciones")
        suggestions.insert(0, "Esta contraseña ha sido filtrada. Elige otra diferente.")

    return PasswordStrengthResponse(
        is_strong=score >= 70 and not is_compromised,
        score=min(score, 100),
        issues=issues,
        is_compromised=is_compromised,
        suggestions=suggestions
    )


async def _send_password_changed_notification(user: User):
    """Envía notificación de cambio de contraseña."""
    subject = "Tu contraseña ha sido cambiada - FinCore"
    html_content = f"""
    <h2>Contraseña Actualizada</h2>
    <p>Tu contraseña de FinCore ha sido cambiada exitosamente.</p>
    <p>Si NO realizaste este cambio, congela tu cuenta inmediatamente y contacta a soporte:</p>
    <a href="{settings.FRONTEND_URL}/security" style="background: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
        Ir a Seguridad
    </a>
    <p><small>Este es un mensaje automático de seguridad.</small></p>
    """

    email_service._send_email(user.email, subject, html_content)


# ============ Verificación de retiro contra whitelist ============

def verify_withdrawal_address(
    user_id: UUID,
    address: str,
    address_type: str,
    db: Session
) -> bool:
    """
    Verifica si una dirección está en la whitelist y puede usarse.

    Esta función debe ser llamada antes de procesar cualquier retiro.

    Returns:
        True si la dirección está activa en la whitelist
    Raises:
        HTTPException si no está permitida
    """
    address_hash = hashlib.sha256(address.lower().encode()).hexdigest()

    whitelist_entry = db.query(WithdrawalWhitelist).filter(
        WithdrawalWhitelist.user_id == user_id,
        WithdrawalWhitelist.address_hash == address_hash,
        WithdrawalWhitelist.address_type == WithdrawalAddressType(address_type)
    ).first()

    if not whitelist_entry:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta dirección no está en tu whitelist. Agrégala primero."
        )

    if whitelist_entry.status == WhitelistStatus.PENDING:
        remaining_hours = (whitelist_entry.quarantine_ends_at - datetime.utcnow()).total_seconds() / 3600
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Esta dirección está en cuarentena. Disponible en {remaining_hours:.1f} horas."
        )

    if whitelist_entry.status != WhitelistStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta dirección no está activa en tu whitelist."
        )

    # Actualizar uso
    whitelist_entry.times_used += 1
    whitelist_entry.last_used_at = datetime.utcnow()
    db.commit()

    return True


def is_account_frozen(user_id: UUID, db: Session) -> bool:
    """Verifica si la cuenta está congelada."""
    freeze = db.query(AccountFreeze).filter(
        AccountFreeze.user_id == user_id,
        AccountFreeze.is_active == True
    ).first()

    return freeze is not None


# ============ Gestión de Dispositivos ============

@router.get("/devices", response_model=DeviceListResponse)
async def list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Listar todos los dispositivos del usuario."""
    device_service = get_device_service(db)
    devices = device_service.get_user_devices(current_user.id)

    # Obtener sesión actual para marcar dispositivo actual
    # (esto se mejoraría pasando el token actual)
    current_device_id = None

    return DeviceListResponse(
        devices=[
            DeviceResponse(
                id=d.id,
                device_name=d.device_name,
                browser_name=d.browser_name,
                os_name=d.os_name,
                device_type=d.device_type,
                last_ip=str(d.last_ip) if d.last_ip else None,
                last_country=d.last_country,
                last_city=d.last_city,
                status=d.status.value,
                is_current=(d.id == current_device_id),
                risk_score=d.risk_score,
                is_vpn=d.is_vpn,
                is_tor=d.is_tor,
                first_seen_at=d.first_seen_at,
                last_seen_at=d.last_seen_at
            )
            for d in devices
        ],
        total=len(devices)
    )


@router.put("/devices/{device_id}")
async def update_device(
    device_id: UUID,
    data: DeviceUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualizar nombre o estado de un dispositivo."""
    device_service = get_device_service(db)

    status = None
    if data.status:
        if data.status == "trusted":
            status = DeviceStatus.TRUSTED
        elif data.status == "blocked":
            status = DeviceStatus.BLOCKED
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Estado inválido. Opciones: trusted, blocked"
            )

    device = device_service.update_device_status(
        device_id=device_id,
        user_id=current_user.id,
        status=status,
        device_name=data.device_name
    )

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispositivo no encontrado"
        )

    # Audit log
    action = AuditAction.DEVICE_TRUSTED if status == DeviceStatus.TRUSTED else AuditAction.DEVICE_BLOCKED
    audit = AuditLog(
        user_id=current_user.id,
        action=action,
        resource_type="UserDevice",
        resource_id=device_id,
        ip_address=request.client.host if request.client else None,
        description=f"Dispositivo actualizado: {device.device_name or device.browser_name}"
    )
    db.add(audit)
    db.commit()

    return {"message": "Dispositivo actualizado"}


@router.delete("/devices/{device_id}")
async def delete_device(
    device_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Eliminar un dispositivo y cerrar sus sesiones."""
    device_service = get_device_service(db)

    # Obtener info antes de eliminar para el log
    device = db.query(UserDevice).filter(
        UserDevice.id == device_id,
        UserDevice.user_id == current_user.id
    ).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispositivo no encontrado"
        )

    device_name = device.device_name or device.browser_name

    success = device_service.delete_device(device_id, current_user.id)

    if success:
        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            action=AuditAction.DEVICE_BLOCKED,
            resource_type="UserDevice",
            ip_address=request.client.host if request.client else None,
            description=f"Dispositivo eliminado: {device_name}"
        )
        db.add(audit)
        db.commit()

        return {"message": "Dispositivo eliminado"}

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Error al eliminar dispositivo"
    )


# ============ Gestión de Sesiones ============

@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Listar todas las sesiones activas del usuario."""
    device_service = get_device_service(db)
    sessions = device_service.get_active_sessions(current_user.id)

    # Detectar sesión actual por IP (simplificado)
    current_ip = request.client.host if request.client else None

    return SessionListResponse(
        sessions=[
            SessionResponse(
                id=s.id,
                device_id=s.device_id,
                device_name=s.device.device_name if s.device else None,
                ip_address=str(s.ip_address) if s.ip_address else None,
                country=s.country,
                city=s.city,
                is_current=(str(s.ip_address) == current_ip if s.ip_address else False),
                created_at=s.created_at,
                last_activity_at=s.last_activity_at,
                expires_at=s.expires_at
            )
            for s in sessions
        ],
        total=len(sessions)
    )


@router.post("/sessions/revoke")
async def revoke_sessions(
    data: RevokeSessionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Revocar sesiones.

    Puede revocar una sesión específica o todas excepto la actual.
    """
    device_service = get_device_service(db)

    if data.revoke_all:
        # Revocar todas excepto la actual
        # Nota: En producción, identificaríamos la sesión actual por el token
        count = device_service.revoke_all_sessions(
            user_id=current_user.id,
            except_session_id=data.session_id  # Opcional: la sesión a mantener
        )

        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            action=AuditAction.ALL_SESSIONS_REVOKED,
            ip_address=request.client.host if request.client else None,
            description=f"Todas las sesiones revocadas ({count} sesiones)"
        )
        db.add(audit)
        db.commit()

        return {"message": f"{count} sesiones cerradas"}

    elif data.session_id:
        success = device_service.revoke_session(data.session_id, current_user.id)

        if success:
            # Audit log
            audit = AuditLog(
                user_id=current_user.id,
                action=AuditAction.SESSION_REVOKED,
                resource_type="UserSession",
                resource_id=data.session_id,
                ip_address=request.client.host if request.client else None,
                description="Sesión revocada remotamente"
            )
            db.add(audit)
            db.commit()

            return {"message": "Sesión cerrada"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión no encontrada"
            )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Especifica session_id o revoke_all=true"
    )


# ============ Actividad de Seguridad ============

@router.get("/activity", response_model=SecurityActivityListResponse)
async def get_security_activity(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener últimos eventos de seguridad del usuario."""
    # Acciones de seguridad relevantes
    security_actions = [
        AuditAction.LOGIN,
        AuditAction.LOGIN_FAILED,
        AuditAction.LOGOUT,
        AuditAction.PASSWORD_CHANGED,
        AuditAction.PASSWORD_RESET_REQUESTED,
        AuditAction.MFA_ENABLED,
        AuditAction.MFA_VERIFIED,
        AuditAction.MFA_BACKUP_CODE_USED,
        AuditAction.WHITELIST_ADDRESS_ADDED,
        AuditAction.WHITELIST_ADDRESS_REMOVED,
        AuditAction.ACCOUNT_FROZEN,
        AuditAction.ACCOUNT_UNFROZEN,
        AuditAction.NEW_DEVICE_DETECTED,
        AuditAction.DEVICE_TRUSTED,
        AuditAction.DEVICE_BLOCKED,
        AuditAction.SESSION_REVOKED,
        AuditAction.ALL_SESSIONS_REVOKED,
    ]

    logs = db.query(AuditLog).filter(
        AuditLog.user_id == current_user.id,
        AuditLog.action.in_(security_actions)
    ).order_by(AuditLog.timestamp.desc()).limit(limit).all()

    return SecurityActivityListResponse(
        activities=[
            SecurityActivityResponse(
                id=log.id,
                action=log.action.value,
                description=log.description or _get_action_description(log.action),
                ip_address=str(log.ip_address) if log.ip_address else None,
                device_info=log.user_agent[:50] if log.user_agent else None,
                country=None,  # TODO: Agregar a audit log
                timestamp=log.timestamp,
                is_suspicious=log.action in [AuditAction.LOGIN_FAILED, AuditAction.NEW_DEVICE_DETECTED]
            )
            for log in logs
        ],
        total=len(logs)
    )


def _get_action_description(action: AuditAction) -> str:
    """Descripción legible de cada acción."""
    descriptions = {
        AuditAction.LOGIN: "Inicio de sesión exitoso",
        AuditAction.LOGIN_FAILED: "Intento de inicio de sesión fallido",
        AuditAction.LOGOUT: "Cierre de sesión",
        AuditAction.PASSWORD_CHANGED: "Contraseña cambiada",
        AuditAction.PASSWORD_RESET_REQUESTED: "Solicitud de recuperación de contraseña",
        AuditAction.MFA_ENABLED: "Autenticación de dos factores activada",
        AuditAction.MFA_VERIFIED: "Código MFA verificado",
        AuditAction.MFA_BACKUP_CODE_USED: "Código de respaldo MFA utilizado",
        AuditAction.WHITELIST_ADDRESS_ADDED: "Nueva dirección de retiro agregada",
        AuditAction.WHITELIST_ADDRESS_REMOVED: "Dirección de retiro eliminada",
        AuditAction.ACCOUNT_FROZEN: "Cuenta congelada",
        AuditAction.ACCOUNT_UNFROZEN: "Cuenta descongelada",
        AuditAction.NEW_DEVICE_DETECTED: "Nuevo dispositivo detectado",
        AuditAction.DEVICE_TRUSTED: "Dispositivo marcado como confiable",
        AuditAction.DEVICE_BLOCKED: "Dispositivo bloqueado",
        AuditAction.SESSION_REVOKED: "Sesión cerrada remotamente",
        AuditAction.ALL_SESSIONS_REVOKED: "Todas las sesiones cerradas",
    }
    return descriptions.get(action, action.value)


# ============ Notificaciones de nuevo dispositivo ============

async def send_new_device_notification(
    user: User,
    device: UserDevice,
    ip_address: str
):
    """Envía notificación de nuevo dispositivo detectado."""
    subject = "Nuevo inicio de sesión detectado - FinCore"

    device_info = f"{device.browser_name or 'Navegador desconocido'} en {device.os_name or 'Sistema desconocido'}"
    location = f"{device.last_city or 'Ciudad desconocida'}, {device.last_country or 'País desconocido'}"

    html_content = f"""
    <h2>Nuevo dispositivo detectado</h2>
    <p>Se ha detectado un inicio de sesión desde un nuevo dispositivo:</p>
    <ul>
        <li><strong>Dispositivo:</strong> {device_info}</li>
        <li><strong>Ubicación:</strong> {location}</li>
        <li><strong>IP:</strong> {ip_address}</li>
        <li><strong>Fecha:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</li>
    </ul>
    <p>Si NO fuiste tú, congela tu cuenta inmediatamente:</p>
    <a href="{settings.FRONTEND_URL}/security" style="background: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
        Revisar Seguridad
    </a>
    <p><small>Si reconoces esta actividad, puedes ignorar este mensaje.</small></p>
    """

    email_service._send_email(user.email, subject, html_content)
