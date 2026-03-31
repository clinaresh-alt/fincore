"""
Endpoints de Autenticacion con MFA.
Implementa login de 2 fases y gestion de tokens.
Incluye device fingerprinting y gestión de sesiones.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, create_mfa_pending_token,
    create_password_reset_token,
    decode_token, generate_mfa_secret, generate_mfa_qr_code, verify_mfa_code
)
from app.models.user import User, UserRole
from app.models.audit import AuditLog, AuditAction
from app.schemas.user import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    MFASetup, MFAVerify, ForgotPasswordRequest, ResetPasswordRequest
)
from app.services.email_service import email_service
from app.services.device_service import DeviceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Autenticacion"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Dependency para obtener usuario actual desde JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invalidas",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if not payload:
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise credentials_exception

    return user


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Dependency para obtener usuario actual de forma opcional (no lanza error si no hay token)."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.replace("Bearer ", "")
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        return None

    return user


def require_role(allowed_roles: list):
    """Dependency factory para verificar roles."""
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.rol not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para esta accion"
            )
        return current_user
    return role_checker


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Registra nuevo usuario.
    Por defecto, MFA esta deshabilitado hasta que el usuario lo active.
    """
    # Verificar email unico
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya esta registrado"
        )

    # Crear usuario
    user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        rol=UserRole(user_data.rol)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action=AuditAction.USER_CREATED,
        resource_type="User",
        resource_id=user.id,
        description=f"Usuario registrado: {user.email}"
    )
    db.add(audit)
    db.commit()

    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login fase 1: Email + Password.
    Si MFA esta habilitado, retorna token temporal para fase 2.
    Incluye device fingerprinting y gestión de sesiones.
    """
    # Buscar usuario
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    # Verificar si esta bloqueado
    if user.bloqueado_hasta and user.bloqueado_hasta > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Cuenta bloqueada hasta {user.bloqueado_hasta}"
        )

    # Obtener IP del cliente
    ip_address = request.client.host if request.client else "127.0.0.1"
    # Considerar headers de proxy (X-Forwarded-For)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()

    # Verificar password
    if not verify_password(form_data.password, user.password_hash):
        user.intentos_fallidos += 1

        # Bloquear despues de N intentos
        if user.intentos_fallidos >= settings.MAX_LOGIN_ATTEMPTS:
            user.bloqueado_hasta = datetime.utcnow() + timedelta(
                minutes=settings.LOCKOUT_DURATION_MINUTES
            )

        db.commit()

        # Audit
        audit = AuditLog(
            user_id=user.id,
            action=AuditAction.LOGIN_FAILED,
            ip_address=ip_address,
            description=f"Intento fallido #{user.intentos_fallidos}"
        )
        db.add(audit)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    # Password correcto - resetear intentos
    user.intentos_fallidos = 0

    # Si MFA habilitado, retornar token temporal (device tracking se hace después de MFA)
    if user.mfa_enabled:
        mfa_token = create_mfa_pending_token(str(user.id))
        # Guardar datos de device en el token para procesarlo después de MFA
        db.commit()

        return TokenResponse(
            access_token="",
            refresh_token="",
            expires_in=0,
            mfa_required=True,
            mfa_token=mfa_token
        )

    # Sin MFA: generar tokens finales
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    user.ultimo_login = datetime.utcnow()

    # === Device Tracking ===
    try:
        device_service = DeviceService(db)
        user_agent = request.headers.get("User-Agent", "")
        accept_language = request.headers.get("Accept-Language")

        # Generar fingerprint del dispositivo
        fingerprint = device_service.generate_device_fingerprint(
            user_agent=user_agent,
            ip_address=ip_address,
            accept_language=accept_language
        )

        # Obtener o crear dispositivo
        device, is_new_device = await device_service.get_or_create_device(
            user=user,
            fingerprint=fingerprint,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Crear sesión
        session = device_service.create_session(
            user=user,
            device=device,
            access_token=access_token,
            refresh_token=refresh_token,
            ip_address=ip_address
        )

        # Notificar si es nuevo dispositivo
        if is_new_device:
            audit_new = AuditLog(
                user_id=user.id,
                action=AuditAction.NEW_DEVICE_DETECTED,
                ip_address=ip_address,
                user_agent=user_agent,
                description=f"Nuevo dispositivo: {device.browser_name} en {device.os_name}, IP: {ip_address}"
            )
            db.add(audit_new)

            # Enviar notificación por email (async en background)
            try:
                email_service.send_new_device_notification(
                    email=user.email,
                    device_name=f"{device.browser_name or 'Navegador'} en {device.os_name or 'Sistema'}",
                    location=f"{device.last_city or 'Desconocido'}, {device.last_country or 'Desconocido'}",
                    ip_address=ip_address,
                    login_time=datetime.utcnow().isoformat()
                )
            except Exception as e:
                logger.warning(f"Error enviando notificación de nuevo dispositivo: {e}")

    except Exception as e:
        logger.error(f"Error en device tracking durante login: {e}")
        # No bloquear login si falla device tracking

    db.commit()

    # Audit
    audit = AuditLog(
        user_id=user.id,
        action=AuditAction.LOGIN,
        ip_address=ip_address
    )
    db.add(audit)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        mfa_required=False
    )


@router.post("/mfa/verify", response_model=TokenResponse)
async def verify_mfa(
    request: Request,
    mfa_data: MFAVerify,
    db: Session = Depends(get_db)
):
    """
    Login fase 2: Verificar codigo MFA (TOTP).
    Incluye device tracking después de verificación exitosa.
    """
    # Decodificar token temporal
    payload = decode_token(mfa_data.mfa_token)
    if not payload or payload.get("type") != "mfa_pending":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token MFA invalido o expirado"
        )

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado"
        )

    # Obtener IP del cliente
    ip_address = request.client.host if request.client else "127.0.0.1"
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()

    # Verificar codigo TOTP
    if not verify_mfa_code(user.mfa_secret, mfa_data.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Codigo MFA incorrecto"
        )

    # Codigo correcto: generar tokens finales
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    user.ultimo_login = datetime.utcnow()

    # === Device Tracking (después de MFA exitoso) ===
    try:
        device_service = DeviceService(db)
        user_agent = request.headers.get("User-Agent", "")
        accept_language = request.headers.get("Accept-Language")

        # Generar fingerprint del dispositivo
        fingerprint = device_service.generate_device_fingerprint(
            user_agent=user_agent,
            ip_address=ip_address,
            accept_language=accept_language
        )

        # Obtener o crear dispositivo
        device, is_new_device = await device_service.get_or_create_device(
            user=user,
            fingerprint=fingerprint,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Crear sesión
        session = device_service.create_session(
            user=user,
            device=device,
            access_token=access_token,
            refresh_token=refresh_token,
            ip_address=ip_address
        )

        # Notificar si es nuevo dispositivo
        if is_new_device:
            audit_new = AuditLog(
                user_id=user.id,
                action=AuditAction.NEW_DEVICE_DETECTED,
                ip_address=ip_address,
                user_agent=user_agent,
                description=f"Nuevo dispositivo: {device.browser_name} en {device.os_name}, IP: {ip_address}"
            )
            db.add(audit_new)

            # Enviar notificación por email
            try:
                email_service.send_new_device_notification(
                    email=user.email,
                    device_name=f"{device.browser_name or 'Navegador'} en {device.os_name or 'Sistema'}",
                    location=f"{device.last_city or 'Desconocido'}, {device.last_country or 'Desconocido'}",
                    ip_address=ip_address,
                    login_time=datetime.utcnow().isoformat()
                )
            except Exception as e:
                logger.warning(f"Error enviando notificación de nuevo dispositivo: {e}")

    except Exception as e:
        logger.error(f"Error en device tracking durante MFA verify: {e}")

    db.commit()

    # Audit
    audit = AuditLog(
        user_id=user.id,
        action=AuditAction.MFA_VERIFIED,
        ip_address=ip_address
    )
    db.add(audit)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        mfa_required=False
    )


@router.post("/mfa/setup", response_model=MFASetup)
async def setup_mfa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Configura MFA para el usuario.
    Genera secreto y QR code para Google Authenticator.
    """
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA ya esta habilitado"
        )

    # Generar secreto
    secret = generate_mfa_secret()

    # Guardar (sin habilitar aun)
    current_user.mfa_secret = secret
    db.commit()

    # Generar QR
    qr_base64 = generate_mfa_qr_code(secret, current_user.email)

    return MFASetup(
        secret=secret,
        qr_code_base64=qr_base64,
        manual_entry_key=secret
    )


@router.post("/mfa/enable")
async def enable_mfa(
    code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Habilita MFA verificando el primer codigo.
    """
    if not current_user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Primero debes configurar MFA con /mfa/setup"
        )

    if not verify_mfa_code(current_user.mfa_secret, code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo incorrecto. Intenta de nuevo."
        )

    current_user.mfa_enabled = True
    db.commit()

    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.MFA_ENABLED,
        description="MFA habilitado exitosamente"
    )
    db.add(audit)
    db.commit()

    return {"message": "MFA habilitado exitosamente"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Obtiene informacion del usuario actual."""
    return current_user


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Renueva el access_token usando un refresh_token válido.
    """
    # Obtener refresh_token del body
    try:
        body = await request.json()
        refresh_token_str = body.get("refresh_token")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token es requerido"
        )

    if not refresh_token_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token es requerido"
        )

    # Decodificar y validar refresh token
    payload = decode_token(refresh_token_str)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalido o expirado"
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no es de tipo refresh"
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido"
        )

    # Verificar que el usuario existe y está activo
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo"
        )

    # Generar nuevos tokens
    new_access_token = create_access_token({"sub": str(user.id)})
    new_refresh_token = create_refresh_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        mfa_required=False
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout - Invalida la sesion.
    En produccion, agregar token a blacklist en Redis.
    """
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.LOGOUT
    )
    db.add(audit)
    db.commit()

    return {"message": "Sesion cerrada"}


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Solicita recuperación de contraseña.
    Genera un token y lo retorna (en producción, enviarlo por email).
    """
    # Buscar usuario por email
    user = db.query(User).filter(User.email == data.email).first()

    # Siempre retornar éxito (no revelar si el email existe)
    if not user:
        return {
            "message": "Si el email existe, recibirás instrucciones para restablecer tu contraseña",
            "success": True
        }

    # Generar token de reset
    reset_token = create_password_reset_token(str(user.id))

    # Enviar email con el link de reset
    email_sent = email_service.send_password_reset_email(user.email, reset_token)

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action=AuditAction.PASSWORD_RESET_REQUESTED,
        ip_address=request.client.host if request.client else None,
        description=f"Solicitud de recuperación de contraseña. Email enviado: {email_sent}"
    )
    db.add(audit)
    db.commit()

    response = {
        "message": "Si el email existe, recibirás instrucciones para restablecer tu contraseña",
        "success": True
    }

    # En modo debug, incluir URL para desarrollo (cuando SendGrid no está configurado)
    if settings.DEBUG and not email_service.is_configured():
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        response["debug_reset_url"] = reset_url

    return response


@router.post("/reset-password")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Restablece la contraseña usando el token de recuperación.
    """
    # Decodificar token
    payload = decode_token(data.token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado"
        )

    # Verificar tipo de token
    if payload.get("type") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido"
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido"
        )

    # Buscar usuario
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # Actualizar contraseña
    user.password_hash = hash_password(data.new_password)
    user.intentos_fallidos = 0  # Reset intentos
    user.bloqueado_hasta = None  # Desbloquear si estaba bloqueado

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action=AuditAction.PASSWORD_CHANGED,
        ip_address=request.client.host if request.client else None,
        description="Contraseña restablecida mediante token de recuperación"
    )
    db.add(audit)
    db.commit()

    return {
        "message": "Contraseña actualizada exitosamente",
        "success": True
    }
