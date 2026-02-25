"""
Schemas de Empresas y Documentos Empresariales.
Validacion y serializacion para gestion de entidades solicitantes.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
import re


# ============================================================
# SCHEMAS DE DOCUMENTOS DE EMPRESA
# ============================================================

class CompanyDocumentCreate(BaseModel):
    """Schema para crear/subir un documento de empresa."""
    tipo: str = Field(..., description="Tipo de documento")
    nombre_original: str = Field(..., min_length=1, max_length=255)
    descripcion: Optional[str] = None
    fecha_emision: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    notas: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "tipo": "Acta Constitutiva",
                "nombre_original": "acta_constitutiva_2020.pdf",
                "descripcion": "Acta constitutiva original",
                "fecha_emision": "2020-01-15"
            }
        }


class CompanyDocumentUpdate(BaseModel):
    """Schema para actualizar metadata de documento."""
    tipo: Optional[str] = None
    descripcion: Optional[str] = None
    fecha_emision: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    notas: Optional[str] = None
    estado: Optional[str] = Field(None, pattern="^(pendiente|aprobado|rechazado)$")
    motivo_rechazo: Optional[str] = None


class CompanyDocumentResponse(BaseModel):
    """Respuesta con datos de documento de empresa."""
    id: UUID
    empresa_id: UUID
    tipo: str
    nombre_archivo: str
    nombre_original: str
    extension: str
    mime_type: str
    tamano_bytes: int
    ruta_archivo: str
    url_descarga: Optional[str] = None
    estado: str
    revisado_por: Optional[UUID] = None
    fecha_revision: Optional[datetime] = None
    motivo_rechazo: Optional[str] = None
    fecha_emision: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    descripcion: Optional[str] = None
    notas: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================
# SCHEMAS DE EMPRESA
# ============================================================

class CompanyBase(BaseModel):
    """Schema base con campos comunes de empresa."""
    # --- Datos Basicos ---
    razon_social: str = Field(..., min_length=3, max_length=255)
    nombre_comercial: Optional[str] = Field(None, max_length=255)
    tipo_empresa: str = Field(default="Persona Moral")
    rfc: str = Field(..., min_length=12, max_length=13)
    curp: Optional[str] = Field(None, min_length=18, max_length=18)

    # --- Datos Fiscales ---
    regimen_fiscal: Optional[str] = Field(None, max_length=100)
    actividad_economica: Optional[str] = Field(None, max_length=255)
    clave_actividad_sat: Optional[str] = Field(None, max_length=10)
    fecha_constitucion: Optional[date] = None
    numero_escritura: Optional[str] = Field(None, max_length=50)
    notaria: Optional[str] = Field(None, max_length=255)
    fecha_inscripcion_rpc: Optional[date] = None

    # --- Direccion Fiscal ---
    calle: Optional[str] = Field(None, max_length=255)
    numero_exterior: Optional[str] = Field(None, max_length=20)
    numero_interior: Optional[str] = Field(None, max_length=20)
    colonia: Optional[str] = Field(None, max_length=100)
    codigo_postal: Optional[str] = Field(None, min_length=5, max_length=5)
    municipio: Optional[str] = Field(None, max_length=100)
    estado: Optional[str] = Field(None, max_length=100)
    pais: str = Field(default="Mexico", max_length=100)

    # --- Contacto ---
    telefono_principal: Optional[str] = Field(None, max_length=20)
    telefono_secundario: Optional[str] = Field(None, max_length=20)
    email_corporativo: Optional[str] = Field(None, max_length=255)
    sitio_web: Optional[str] = Field(None, max_length=255)

    # --- Representante Legal ---
    representante_nombre: Optional[str] = Field(None, max_length=255)
    representante_cargo: Optional[str] = Field(None, max_length=100)
    representante_email: Optional[str] = Field(None, max_length=255)
    representante_telefono: Optional[str] = Field(None, max_length=20)
    representante_rfc: Optional[str] = Field(None, max_length=13)
    representante_curp: Optional[str] = Field(None, max_length=18)

    # --- Informacion Financiera ---
    tamano_empresa: Optional[str] = None
    numero_empleados: Optional[int] = Field(None, ge=0)
    ingresos_anuales: Optional[Decimal] = Field(None, ge=0)
    capital_social: Optional[Decimal] = Field(None, ge=0)
    antiguedad_anos: Optional[int] = Field(None, ge=0)

    # --- Sector e Industria ---
    sector: Optional[str] = Field(None, max_length=100)
    industria: Optional[str] = Field(None, max_length=100)
    giro: Optional[str] = Field(None, max_length=255)

    # --- Informacion Bancaria ---
    banco: Optional[str] = Field(None, max_length=100)
    cuenta_clabe: Optional[str] = Field(None, min_length=18, max_length=18)
    cuenta_numero: Optional[str] = Field(None, max_length=20)

    @field_validator('rfc')
    @classmethod
    def validate_rfc(cls, v: str) -> str:
        """Valida formato basico de RFC mexicano."""
        if v:
            v = v.upper().strip()
            # RFC persona moral: 3 letras + 6 digitos + 3 alfanumericos = 12
            # RFC persona fisica: 4 letras + 6 digitos + 3 alfanumericos = 13
            pattern = r'^[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}$'
            if not re.match(pattern, v):
                raise ValueError('RFC invalido. Formato esperado: 3-4 letras + 6 digitos + 3 alfanumericos')
        return v

    @field_validator('curp')
    @classmethod
    def validate_curp(cls, v: Optional[str]) -> Optional[str]:
        """Valida formato de CURP mexicano."""
        if v:
            v = v.upper().strip()
            pattern = r'^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$'
            if not re.match(pattern, v):
                raise ValueError('CURP invalido')
        return v

    @field_validator('cuenta_clabe')
    @classmethod
    def validate_clabe(cls, v: Optional[str]) -> Optional[str]:
        """Valida formato de CLABE interbancaria."""
        if v:
            v = v.strip()
            if not v.isdigit() or len(v) != 18:
                raise ValueError('CLABE debe ser de 18 digitos')
        return v

    @field_validator('codigo_postal')
    @classmethod
    def validate_codigo_postal(cls, v: Optional[str]) -> Optional[str]:
        """Valida codigo postal mexicano."""
        if v:
            v = v.strip()
            if not v.isdigit() or len(v) != 5:
                raise ValueError('Codigo postal debe ser de 5 digitos')
        return v


class CompanyCreate(CompanyBase):
    """Schema para crear empresa."""
    datos_adicionales: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "razon_social": "Tecnologias Innovadoras S.A. de C.V.",
                "nombre_comercial": "TecnoInnova",
                "tipo_empresa": "S.A. de C.V.",
                "rfc": "TIN200115ABC",
                "regimen_fiscal": "General de Ley Personas Morales",
                "actividad_economica": "Desarrollo de software",
                "calle": "Av. Reforma",
                "numero_exterior": "123",
                "colonia": "Juarez",
                "codigo_postal": "06600",
                "municipio": "Cuauhtemoc",
                "estado": "Ciudad de Mexico",
                "telefono_principal": "5555551234",
                "email_corporativo": "contacto@tecnoinnova.com",
                "representante_nombre": "Juan Perez Garcia",
                "representante_cargo": "Director General",
                "tamano_empresa": "Pequena",
                "numero_empleados": 25,
                "ingresos_anuales": 5000000.00,
                "sector": "Tecnologia",
                "industria": "Software"
            }
        }


class CompanyUpdate(BaseModel):
    """Schema para actualizar empresa (todos los campos opcionales)."""
    # --- Datos Basicos ---
    razon_social: Optional[str] = Field(None, min_length=3, max_length=255)
    nombre_comercial: Optional[str] = Field(None, max_length=255)
    tipo_empresa: Optional[str] = None
    curp: Optional[str] = Field(None, min_length=18, max_length=18)

    # --- Datos Fiscales ---
    regimen_fiscal: Optional[str] = Field(None, max_length=100)
    actividad_economica: Optional[str] = Field(None, max_length=255)
    clave_actividad_sat: Optional[str] = Field(None, max_length=10)
    fecha_constitucion: Optional[date] = None
    numero_escritura: Optional[str] = Field(None, max_length=50)
    notaria: Optional[str] = Field(None, max_length=255)
    fecha_inscripcion_rpc: Optional[date] = None

    # --- Direccion Fiscal ---
    calle: Optional[str] = Field(None, max_length=255)
    numero_exterior: Optional[str] = Field(None, max_length=20)
    numero_interior: Optional[str] = Field(None, max_length=20)
    colonia: Optional[str] = Field(None, max_length=100)
    codigo_postal: Optional[str] = Field(None, min_length=5, max_length=5)
    municipio: Optional[str] = Field(None, max_length=100)
    estado: Optional[str] = Field(None, max_length=100)
    pais: Optional[str] = Field(None, max_length=100)

    # --- Contacto ---
    telefono_principal: Optional[str] = Field(None, max_length=20)
    telefono_secundario: Optional[str] = Field(None, max_length=20)
    email_corporativo: Optional[str] = Field(None, max_length=255)
    sitio_web: Optional[str] = Field(None, max_length=255)

    # --- Representante Legal ---
    representante_nombre: Optional[str] = Field(None, max_length=255)
    representante_cargo: Optional[str] = Field(None, max_length=100)
    representante_email: Optional[str] = Field(None, max_length=255)
    representante_telefono: Optional[str] = Field(None, max_length=20)
    representante_rfc: Optional[str] = Field(None, max_length=13)
    representante_curp: Optional[str] = Field(None, max_length=18)

    # --- Informacion Financiera ---
    tamano_empresa: Optional[str] = None
    numero_empleados: Optional[int] = Field(None, ge=0)
    ingresos_anuales: Optional[Decimal] = Field(None, ge=0)
    capital_social: Optional[Decimal] = Field(None, ge=0)
    antiguedad_anos: Optional[int] = Field(None, ge=0)

    # --- Sector e Industria ---
    sector: Optional[str] = Field(None, max_length=100)
    industria: Optional[str] = Field(None, max_length=100)
    giro: Optional[str] = Field(None, max_length=255)

    # --- Informacion Bancaria ---
    banco: Optional[str] = Field(None, max_length=100)
    cuenta_clabe: Optional[str] = Field(None, min_length=18, max_length=18)
    cuenta_numero: Optional[str] = Field(None, max_length=20)

    # --- Metadata ---
    datos_adicionales: Optional[dict] = None
    notas_verificacion: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "nombre_comercial": "Nuevo Nombre Comercial",
                "numero_empleados": 30,
                "ingresos_anuales": 6000000.00
            }
        }


class CompanyResponse(BaseModel):
    """Respuesta con datos completos de empresa."""
    id: UUID
    razon_social: str
    nombre_comercial: Optional[str] = None
    tipo_empresa: str
    rfc: str
    curp: Optional[str] = None

    # Datos Fiscales
    regimen_fiscal: Optional[str] = None
    actividad_economica: Optional[str] = None
    clave_actividad_sat: Optional[str] = None
    fecha_constitucion: Optional[date] = None
    numero_escritura: Optional[str] = None
    notaria: Optional[str] = None
    fecha_inscripcion_rpc: Optional[date] = None

    # Direccion
    calle: Optional[str] = None
    numero_exterior: Optional[str] = None
    numero_interior: Optional[str] = None
    colonia: Optional[str] = None
    codigo_postal: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    pais: str = "Mexico"
    direccion_completa: Optional[str] = None

    # Contacto
    telefono_principal: Optional[str] = None
    telefono_secundario: Optional[str] = None
    email_corporativo: Optional[str] = None
    sitio_web: Optional[str] = None

    # Representante Legal
    representante_nombre: Optional[str] = None
    representante_cargo: Optional[str] = None
    representante_email: Optional[str] = None
    representante_telefono: Optional[str] = None
    representante_rfc: Optional[str] = None
    representante_curp: Optional[str] = None

    # Informacion Financiera
    tamano_empresa: Optional[str] = None
    numero_empleados: Optional[int] = None
    ingresos_anuales: Optional[Decimal] = None
    capital_social: Optional[Decimal] = None
    antiguedad_anos: Optional[int] = None

    # Sector
    sector: Optional[str] = None
    industria: Optional[str] = None
    giro: Optional[str] = None

    # Bancaria
    banco: Optional[str] = None
    cuenta_clabe: Optional[str] = None
    cuenta_numero: Optional[str] = None

    # Estado y Verificacion
    estado_verificacion: str
    fecha_verificacion: Optional[datetime] = None
    verificado_por: Optional[UUID] = None
    notas_verificacion: Optional[str] = None
    score_riesgo: Optional[int] = None

    # Metadata
    datos_adicionales: Optional[dict] = None
    user_id: UUID

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Relaciones (conteos)
    total_documentos: Optional[int] = None
    total_proyectos: Optional[int] = None

    class Config:
        from_attributes = True


class CompanyListItem(BaseModel):
    """Item de lista de empresas (version resumida)."""
    id: UUID
    razon_social: str
    nombre_comercial: Optional[str] = None
    tipo_empresa: str
    rfc: str
    estado_verificacion: str
    sector: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    total_proyectos: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CompanyListResponse(BaseModel):
    """Respuesta paginada de lista de empresas."""
    items: List[CompanyListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class CompanyWithDocuments(CompanyResponse):
    """Empresa con lista de documentos."""
    documentos: List[CompanyDocumentResponse] = []


class CompanyVerificationUpdate(BaseModel):
    """Schema para actualizar estado de verificacion."""
    estado_verificacion: str = Field(..., pattern="^(Pendiente|En Revision|Verificada|Activa|Suspendida|Rechazada)$")
    notas_verificacion: Optional[str] = None
    score_riesgo: Optional[int] = Field(None, ge=0, le=100)

    class Config:
        json_schema_extra = {
            "example": {
                "estado_verificacion": "Verificada",
                "notas_verificacion": "Documentacion completa y validada",
                "score_riesgo": 85
            }
        }


# ============================================================
# SCHEMAS DE TIPOS Y CONSTANTES
# ============================================================

class CompanyTypeOption(BaseModel):
    """Opcion de tipo de empresa."""
    value: str
    label: str


class CompanyTypesResponse(BaseModel):
    """Lista de tipos de empresa disponibles."""
    tipos_empresa: List[CompanyTypeOption]
    tamanos_empresa: List[CompanyTypeOption]
    estados_verificacion: List[CompanyTypeOption]
    tipos_documento: List[CompanyTypeOption]
