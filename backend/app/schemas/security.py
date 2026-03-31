"""
Schemas Pydantic para funcionalidades de Seguridad.

Incluye:
- Whitelist de retiros
- Anti-phishing
- Backup codes MFA
- Gestión de dispositivos y sesiones
- Congelamiento de cuenta
- Historial de contraseñas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
import re


# ============ Whitelist de Retiros ============

class WithdrawalAddressCreate(BaseModel):
    """Crear nueva dirección de retiro."""
    address_type: str = Field(..., description="Tipo: crypto_erc20, crypto_trc20, bank_clabe, bank_iban")
    address: str = Field(..., min_length=10, max_length=255)
    label: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("address_type")
    @classmethod
    def validate_address_type(cls, v):
        valid_types = ["crypto_erc20", "crypto_trc20", "bank_clabe", "bank_iban", "bank_ach"]
        if v not in valid_types:
            raise ValueError(f"Tipo inválido. Opciones: {valid_types}")
        return v

    @field_validator("address")
    @classmethod
    def validate_address(cls, v, info):
        address_type = info.data.get("address_type", "")

        if address_type in ["crypto_erc20"]:
            # Ethereum-like address
            if not re.match(r"^0x[a-fA-F0-9]{40}$", v):
                raise ValueError("Dirección ERC-20 inválida (debe ser 0x seguido de 40 caracteres hex)")

        elif address_type == "crypto_trc20":
            # TRON address
            if not re.match(r"^T[a-zA-Z0-9]{33}$", v):
                raise ValueError("Dirección TRC-20 inválida (debe empezar con T y tener 34 caracteres)")

        elif address_type == "bank_clabe":
            # CLABE mexicana
            if not re.match(r"^\d{18}$", v):
                raise ValueError("CLABE inválida (debe ser 18 dígitos)")

        elif address_type == "bank_iban":
            # IBAN internacional (formato básico)
            if not re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$", v.upper()):
                raise ValueError("IBAN inválido")

        return v


class WithdrawalAddressResponse(BaseModel):
    """Respuesta de dirección de retiro."""
    id: UUID
    address_type: str
    address: str
    address_masked: Optional[str] = None
    label: Optional[str]
    status: str
    is_in_quarantine: bool
    quarantine_ends_at: Optional[datetime]
    can_be_used: bool
    is_primary: bool
    times_used: int
    last_used_at: Optional[datetime]
    created_at: datetime
    activated_at: Optional[datetime]

    class Config:
        from_attributes = True


class WhitelistListResponse(BaseModel):
    """Lista de direcciones en whitelist."""
    addresses: List[WithdrawalAddressResponse]
    total: int


class CancelWhitelistRequest(BaseModel):
    """Cancelar dirección en cuarentena."""
    cancellation_token: str = Field(..., min_length=32)


# ============ Anti-Phishing ============

class AntiPhishingSetup(BaseModel):
    """Configurar frase anti-phishing."""
    phrase: str = Field(
        ...,
        min_length=4,
        max_length=50,
        description="Frase secreta que aparecerá en todos los emails"
    )
    phrase_hint: Optional[str] = Field(
        None,
        max_length=100,
        description="Pista para recordar la frase"
    )

    @field_validator("phrase")
    @classmethod
    def validate_phrase(cls, v):
        # No permitir frases muy comunes
        common_phrases = ["password", "123456", "qwerty", "admin", "test"]
        if v.lower() in common_phrases:
            raise ValueError("La frase es muy común, elige una más segura")
        return v


class AntiPhishingResponse(BaseModel):
    """Respuesta de frase anti-phishing."""
    is_configured: bool
    phrase_hint: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class AntiPhishingVerify(BaseModel):
    """Verificar autenticidad de email."""
    email_id: str = Field(..., description="ID del email a verificar")


# ============ Backup Codes MFA ============

class MFABackupCodesResponse(BaseModel):
    """Respuesta con códigos de respaldo MFA."""
    codes: List[str] = Field(..., description="8 códigos de un solo uso")
    warning: str = Field(
        default="Guarda estos códigos en un lugar seguro. "
                "Solo se mostrarán una vez y no podrán recuperarse."
    )
    generated_at: datetime


class MFABackupCodeVerify(BaseModel):
    """Verificar código de respaldo."""
    code: str = Field(..., min_length=9, max_length=9)  # Formato: XXXX-XXXX

    @field_validator("code")
    @classmethod
    def validate_code_format(cls, v):
        if not re.match(r"^[A-F0-9]{4}-[A-F0-9]{4}$", v.upper()):
            raise ValueError("Formato de código inválido (debe ser XXXX-XXXX)")
        return v.upper()


class MFABackupCodesStatus(BaseModel):
    """Estado de códigos de respaldo."""
    total_codes: int
    used_codes: int
    remaining_codes: int
    last_used_at: Optional[datetime]


# ============ Gestión de Dispositivos ============

class DeviceResponse(BaseModel):
    """Respuesta de dispositivo registrado."""
    id: UUID
    device_name: Optional[str]
    browser_name: Optional[str]
    os_name: Optional[str]
    device_type: Optional[str]
    last_ip: Optional[str]
    last_country: Optional[str]
    last_city: Optional[str]
    status: str
    is_current: bool = False
    risk_score: int
    is_vpn: bool
    is_tor: bool
    first_seen_at: datetime
    last_seen_at: datetime

    class Config:
        from_attributes = True


class DeviceListResponse(BaseModel):
    """Lista de dispositivos."""
    devices: List[DeviceResponse]
    total: int


class DeviceUpdate(BaseModel):
    """Actualizar dispositivo."""
    device_name: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, description="trusted, blocked")


# ============ Gestión de Sesiones ============

class SessionResponse(BaseModel):
    """Respuesta de sesión activa."""
    id: UUID
    device_id: Optional[UUID]
    device_name: Optional[str]
    ip_address: Optional[str]
    country: Optional[str]
    city: Optional[str]
    is_current: bool
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """Lista de sesiones activas."""
    sessions: List[SessionResponse]
    total: int


class RevokeSessionRequest(BaseModel):
    """Revocar sesión."""
    session_id: Optional[UUID] = Field(None, description="ID de sesión específica")
    revoke_all: bool = Field(False, description="Revocar todas excepto la actual")


# ============ Congelamiento de Cuenta ============

class FreezeAccountRequest(BaseModel):
    """Solicitar congelamiento de cuenta."""
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Razón del congelamiento (opcional)"
    )


class FreezeAccountResponse(BaseModel):
    """Respuesta de congelamiento."""
    is_frozen: bool
    frozen_at: datetime
    reason: str
    unfreeze_instructions: str


class UnfreezeAccountRequest(BaseModel):
    """Descongelar cuenta."""
    unfreeze_token: str = Field(..., min_length=32)


# ============ Contraseñas ============

class PasswordChangeRequest(BaseModel):
    """Cambiar contraseña."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v, info):
        errors = []

        if len(v) < 12:
            errors.append("mínimo 12 caracteres")
        if not re.search(r"[A-Z]", v):
            errors.append("al menos una mayúscula")
        if not re.search(r"[a-z]", v):
            errors.append("al menos una minúscula")
        if not re.search(r"\d", v):
            errors.append("al menos un número")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            errors.append("al menos un símbolo especial")

        if errors:
            raise ValueError(f"Contraseña débil: {', '.join(errors)}")

        # Verificar que no sea igual a la actual
        current = info.data.get("current_password")
        if current and v == current:
            raise ValueError("La nueva contraseña debe ser diferente a la actual")

        return v


class PasswordStrengthResponse(BaseModel):
    """Resultado de verificación de contraseña."""
    is_strong: bool
    score: int  # 0-100
    issues: List[str]
    is_compromised: bool  # HIBP check
    suggestions: List[str]


# ============ Actividad de Seguridad ============

class SecurityActivityResponse(BaseModel):
    """Evento de actividad de seguridad."""
    id: UUID
    action: str
    description: str
    ip_address: Optional[str]
    device_info: Optional[str]
    country: Optional[str]
    timestamp: datetime
    is_suspicious: bool = False


class SecurityActivityListResponse(BaseModel):
    """Lista de actividad de seguridad."""
    activities: List[SecurityActivityResponse]
    total: int


# ============ Resumen de Seguridad ============

class SecuritySummaryResponse(BaseModel):
    """Resumen del estado de seguridad de la cuenta."""
    # MFA
    mfa_enabled: bool
    mfa_backup_codes_remaining: int

    # Anti-phishing
    anti_phishing_configured: bool

    # Dispositivos
    total_devices: int
    trusted_devices: int

    # Sesiones
    active_sessions: int

    # Whitelist
    whitelisted_addresses: int
    addresses_in_quarantine: int

    # Cuenta
    is_frozen: bool
    password_last_changed: Optional[datetime]
    password_expires_at: Optional[datetime]

    # Score general
    security_score: int  # 0-100
    recommendations: List[str]
