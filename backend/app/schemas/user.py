"""
Schemas de Usuario y Autenticacion.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


# === AUTH ===

class UserCreate(BaseModel):
    """Schema para registro de usuario."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    rol: str = Field(default="Cliente", pattern="^(Cliente|Inversionista)$")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "usuario@ejemplo.com",
                "password": "SecurePass123!",
                "rol": "Inversionista"
            }
        }


class UserLogin(BaseModel):
    """Schema para login fase 1."""
    email: EmailStr
    password: str


class MFASetup(BaseModel):
    """Respuesta de configuracion MFA."""
    secret: str
    qr_code_base64: str
    manual_entry_key: str


class MFAVerify(BaseModel):
    """Schema para verificar codigo MFA."""
    code: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]{6}$")
    mfa_token: str  # Token temporal de sesion pendiente


class TokenResponse(BaseModel):
    """Respuesta con tokens JWT."""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # Segundos
    mfa_required: bool = False
    mfa_token: Optional[str] = None  # Token temporal si requiere MFA


class UserResponse(BaseModel):
    """Respuesta con datos de usuario."""
    id: UUID
    email: str
    rol: str
    mfa_enabled: bool
    email_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


# === PROFILE (KYC) ===

class UserProfileCreate(BaseModel):
    """Schema para crear perfil con datos fiscales."""
    tax_id: str = Field(..., min_length=10, max_length=20)
    nombre_legal: str = Field(..., min_length=3, max_length=255)
    tipo_persona: str = Field(..., pattern="^(Fisica|Juridica)$")
    pais: str = Field(default="MX", min_length=2, max_length=2)

    # Direccion fiscal
    direccion_fiscal: Optional[str] = None
    ciudad: Optional[str] = None
    estado_provincia: Optional[str] = None
    codigo_postal: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "tax_id": "ABC123456XYZ",
                "nombre_legal": "Inversiones Globales S.A. de C.V.",
                "tipo_persona": "Juridica",
                "pais": "MX",
                "direccion_fiscal": "Av. Reforma 123, Col. Centro",
                "ciudad": "Ciudad de Mexico",
                "codigo_postal": "06600"
            }
        }


class UserProfileResponse(BaseModel):
    """Respuesta con perfil de usuario."""
    id: UUID
    tax_id: str
    nombre_legal: str
    tipo_persona: str
    verificado_kyc: bool
    kyc_score: Optional[int]
    situacion_tributaria: Optional[dict]
    fecha_validacion_tax: Optional[datetime]

    class Config:
        from_attributes = True


class TaxValidationRequest(BaseModel):
    """Request para validar ID fiscal."""
    tax_id: str
    country_code: str = "MX"
    legal_name: Optional[str] = None


class TaxValidationResponse(BaseModel):
    """Respuesta de validacion fiscal."""
    is_valid: bool
    tax_status: Optional[str]
    verification_date: datetime
    kyc_score: Optional[int]
    message: Optional[str]
