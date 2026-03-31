"""
Modulo de Seguridad de Grado Bancario.
Incluye: Hashing, JWT, MFA (TOTP), Cifrado AES-256.
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
import secrets

from jose import jwt, JWTError
import bcrypt
import pyotp
import qrcode
import qrcode.image.svg
from io import BytesIO
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings

# Password Hashing (bcrypt directo para compatibilidad con bcrypt 4.1+)

def hash_password(password: str) -> str:
    """Hash de password con bcrypt."""
    # Truncar a 72 bytes para bcrypt (limite del algoritmo)
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica password contra hash."""
    password_bytes = plain_password.encode('utf-8')[:72]
    return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))


# JWT Token Management
def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Crea JWT de acceso con expiracion corta (15 min por defecto).
    Para seguridad bancaria, tokens de corta duracion.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({
        "exp": expire,
        "type": "access"
    })
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token(data: dict) -> str:
    """
    Crea Refresh Token con expiracion larga (7 dias).
    Se almacena en HttpOnly Cookie.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "type": "refresh"
    })
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def create_mfa_pending_token(user_id: str) -> str:
    """
    Token temporal para sesion pendiente de MFA.
    Expira en 5 minutos.
    """
    to_encode = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(minutes=5),
        "type": "mfa_pending"
    }
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def create_password_reset_token(user_id: str) -> str:
    """
    Token para recuperación de contraseña.
    Expira en 1 hora.
    """
    to_encode = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(hours=1),
        "type": "password_reset"
    }
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def decode_token(token: str) -> Optional[dict]:
    """Decodifica y valida un JWT."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


# MFA (TOTP - Google Authenticator)
def generate_mfa_secret() -> str:
    """Genera secreto para TOTP (compatible con Google Authenticator)."""
    return pyotp.random_base32()


def get_mfa_uri(secret: str, email: str) -> str:
    """
    Genera URI para QR code de Google Authenticator.
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(
        name=email,
        issuer_name=settings.MFA_ISSUER_NAME
    )


def generate_mfa_qr_code(secret: str, email: str) -> str:
    """
    Genera QR code en base64 para mostrar en frontend.
    El usuario lo escanea con Google Authenticator.
    """
    uri = get_mfa_uri(secret, email)
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def verify_mfa_code(secret: str, code: str) -> bool:
    """
    Verifica codigo TOTP de 6 digitos.
    Acepta codigo actual y 1 codigo anterior (30 segundos de tolerancia).
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# AES-256 Encryption (para datos sensibles)
def _get_fernet_key() -> bytes:
    """Deriva clave Fernet desde la clave de configuracion."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"fincore_salt_v1",  # En produccion, usar salt unico por registro
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(
        kdf.derive(settings.ENCRYPTION_KEY.encode())
    )
    return key


def encrypt_sensitive_data(data: str) -> str:
    """
    Cifra datos sensibles (ID fiscal, datos bancarios) con AES-256.
    Retorna string base64.
    """
    fernet = Fernet(_get_fernet_key())
    return fernet.encrypt(data.encode()).decode()


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Descifra datos sensibles."""
    fernet = Fernet(_get_fernet_key())
    return fernet.decrypt(encrypted_data.encode()).decode()


# Aliases para compatibilidad
encrypt_data = encrypt_sensitive_data
decrypt_data = decrypt_sensitive_data


# ============ Dependencia de autenticación FastAPI ============
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(lambda: None)  # Se inyecta get_db en el endpoint
):
    """
    Dependencia de FastAPI para obtener el usuario actual desde JWT.
    Se usa como: current_user: User = Depends(get_current_user)
    """
    from app.core.database import get_db
    from app.models.user import User

    # Obtener sesión de DB correctamente
    db_gen = get_db()
    db = next(db_gen)

    try:
        payload = decode_token(token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verificar tipo de token
        token_type = payload.get("type")
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tipo de token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario desactivado"
            )

        return user
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


# ============ HIBP (Have I Been Pwned) Password Check ============
import httpx
import hashlib as _hashlib


async def check_password_hibp(password: str) -> tuple[bool, int]:
    """
    Verifica si una contraseña ha sido comprometida usando la API de HIBP.

    Usa el modelo k-anonymity: solo envía los primeros 5 caracteres del hash SHA-1.

    Returns:
        tuple: (is_compromised, count) - Si está comprometida y cuántas veces
    """
    # Calcular SHA-1 de la contraseña
    sha1_hash = _hashlib.sha1(password.encode()).hexdigest().upper()
    prefix = sha1_hash[:5]
    suffix = sha1_hash[5:]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                headers={"User-Agent": "FinCore-Security-Check"},
                timeout=5.0
            )

            if response.status_code != 200:
                # Si falla la API, no bloquear al usuario
                return (False, 0)

            # Buscar el sufijo en la respuesta
            hashes = response.text.splitlines()
            for line in hashes:
                parts = line.split(":")
                if len(parts) == 2 and parts[0] == suffix:
                    count = int(parts[1])
                    return (True, count)

            return (False, 0)

    except Exception:
        # Si hay error de red, no bloquear
        return (False, 0)


def check_password_hibp_sync(password: str) -> tuple[bool, int]:
    """Versión síncrona del check HIBP."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(check_password_hibp(password))
    except RuntimeError:
        # Si no hay event loop, crear uno nuevo
        return asyncio.run(check_password_hibp(password))
