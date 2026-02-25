"""
Modelo de Empresas/Entidades Solicitantes.
Gestion de empresas propietarias de proyectos de inversion.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime,
    Text, ForeignKey, Enum as SQLEnum, Numeric, Date
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Index
import enum

from app.core.database import Base


class CompanyType(str, enum.Enum):
    """Tipos de empresa/entidad."""
    PERSONA_FISICA = "Persona Fisica"
    PERSONA_MORAL = "Persona Moral"
    SOCIEDAD_ANONIMA = "S.A."
    SOCIEDAD_ANONIMA_CV = "S.A. de C.V."
    SOCIEDAD_RL = "S. de R.L."
    SOCIEDAD_RL_CV = "S. de R.L. de C.V."
    SAPI = "S.A.P.I."
    SAPI_CV = "S.A.P.I. de C.V."
    ASOCIACION_CIVIL = "A.C."
    SOCIEDAD_CIVIL = "S.C."
    FIDEICOMISO = "Fideicomiso"
    OTRO = "Otro"


class CompanySize(str, enum.Enum):
    """Tamano de empresa segun INEGI."""
    MICRO = "Micro"       # 1-10 empleados
    PEQUENA = "Pequena"   # 11-50 empleados
    MEDIANA = "Mediana"   # 51-250 empleados
    GRANDE = "Grande"     # 250+ empleados


class CompanyStatus(str, enum.Enum):
    """Estado de la empresa en el sistema."""
    PENDIENTE = "Pendiente"           # Recien registrada
    EN_REVISION = "En Revision"       # Documentos en revision
    VERIFICADA = "Verificada"         # KYC aprobado
    ACTIVA = "Activa"                 # Puede crear proyectos
    SUSPENDIDA = "Suspendida"         # Temporalmente bloqueada
    RECHAZADA = "Rechazada"           # KYC fallido


class CompanyDocumentType(str, enum.Enum):
    """Tipos de documento requeridos para empresas."""
    ACTA_CONSTITUTIVA = "Acta Constitutiva"
    RFC = "Constancia de Situacion Fiscal RFC"
    PODER_NOTARIAL = "Poder Notarial del Representante"
    INE_REPRESENTANTE = "INE del Representante Legal"
    COMPROBANTE_DOMICILIO = "Comprobante de Domicilio Fiscal"
    ESTADOS_FINANCIEROS = "Estados Financieros Auditados"
    DECLARACION_ANUAL = "Declaracion Anual de Impuestos"
    OPINION_CUMPLIMIENTO = "Opinion de Cumplimiento SAT"
    CEDULA_FISCAL = "Cedula de Identificacion Fiscal"
    CONTRATO_SOCIAL = "Contrato Social"
    ACTA_ASAMBLEA = "Acta de Asamblea"
    CURRICULUM_EMPRESA = "Curriculum Empresarial"
    CARTERA_CLIENTES = "Cartera de Clientes"
    CERTIFICACIONES = "Certificaciones y Licencias"
    OTRO = "Otro Documento"


class Company(Base):
    """
    Empresas/Entidades solicitantes de financiamiento.
    Una empresa puede tener multiples proyectos.
    """
    __tablename__ = "empresas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # --- Datos Basicos ---
    razon_social = Column(String(255), nullable=False)
    nombre_comercial = Column(String(255), nullable=True)
    tipo_empresa = Column(
        SQLEnum(CompanyType, name="company_type_enum"),
        default=CompanyType.PERSONA_MORAL
    )
    rfc = Column(String(13), nullable=False, unique=True)  # RFC unico
    curp = Column(String(18), nullable=True)  # Solo para persona fisica

    # --- Datos Fiscales ---
    regimen_fiscal = Column(String(100), nullable=True)
    actividad_economica = Column(String(255), nullable=True)
    clave_actividad_sat = Column(String(10), nullable=True)
    fecha_constitucion = Column(Date, nullable=True)
    numero_escritura = Column(String(50), nullable=True)
    notaria = Column(String(255), nullable=True)
    fecha_inscripcion_rpc = Column(Date, nullable=True)  # Registro Publico de Comercio

    # --- Direccion Fiscal ---
    calle = Column(String(255), nullable=True)
    numero_exterior = Column(String(20), nullable=True)
    numero_interior = Column(String(20), nullable=True)
    colonia = Column(String(100), nullable=True)
    codigo_postal = Column(String(5), nullable=True)
    municipio = Column(String(100), nullable=True)
    estado = Column(String(100), nullable=True)
    pais = Column(String(100), default="Mexico")

    # --- Contacto ---
    telefono_principal = Column(String(20), nullable=True)
    telefono_secundario = Column(String(20), nullable=True)
    email_corporativo = Column(String(255), nullable=True)
    sitio_web = Column(String(255), nullable=True)

    # --- Representante Legal ---
    representante_nombre = Column(String(255), nullable=True)
    representante_cargo = Column(String(100), nullable=True)
    representante_email = Column(String(255), nullable=True)
    representante_telefono = Column(String(20), nullable=True)
    representante_rfc = Column(String(13), nullable=True)
    representante_curp = Column(String(18), nullable=True)

    # --- Informacion Financiera ---
    tamano_empresa = Column(
        SQLEnum(CompanySize, name="company_size_enum"),
        nullable=True
    )
    numero_empleados = Column(Integer, nullable=True)
    ingresos_anuales = Column(Numeric(18, 2), nullable=True)
    capital_social = Column(Numeric(18, 2), nullable=True)
    antiguedad_anos = Column(Integer, nullable=True)

    # --- Sector e Industria ---
    sector = Column(String(100), nullable=True)
    industria = Column(String(100), nullable=True)
    giro = Column(String(255), nullable=True)

    # --- Informacion Bancaria ---
    banco = Column(String(100), nullable=True)
    cuenta_clabe = Column(String(18), nullable=True)
    cuenta_numero = Column(String(20), nullable=True)

    # --- Estado y Verificacion ---
    estado_verificacion = Column(
        SQLEnum(CompanyStatus, name="company_status_enum"),
        default=CompanyStatus.PENDIENTE
    )
    fecha_verificacion = Column(DateTime(timezone=True), nullable=True)
    verificado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    notas_verificacion = Column(Text, nullable=True)
    score_riesgo = Column(Integer, nullable=True)  # 0-100

    # --- Metadata ---
    datos_adicionales = Column(JSONB, nullable=True)  # Datos extra flexibles

    # --- Usuario propietario ---
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    # --- Relaciones ---
    user = relationship("User", back_populates="companies", foreign_keys=[user_id])
    documentos = relationship("CompanyDocument", back_populates="company", cascade="all, delete-orphan")
    proyectos = relationship("Project", back_populates="empresa")

    __table_args__ = (
        Index("idx_empresa_rfc", "rfc"),
        Index("idx_empresa_razon_social", "razon_social"),
        Index("idx_empresa_estado", "estado_verificacion"),
        Index("idx_empresa_user", "user_id"),
    )

    def __repr__(self):
        return f"<Company {self.razon_social} ({self.rfc})>"

    @property
    def direccion_completa(self) -> str:
        """Retorna la direccion completa formateada."""
        partes = []
        if self.calle:
            partes.append(self.calle)
        if self.numero_exterior:
            partes.append(f"No. {self.numero_exterior}")
        if self.numero_interior:
            partes.append(f"Int. {self.numero_interior}")
        if self.colonia:
            partes.append(f"Col. {self.colonia}")
        if self.codigo_postal:
            partes.append(f"C.P. {self.codigo_postal}")
        if self.municipio:
            partes.append(self.municipio)
        if self.estado:
            partes.append(self.estado)
        return ", ".join(partes) if partes else ""


class CompanyDocument(Base):
    """
    Documentos asociados a una empresa.
    Requeridos para verificacion KYC.
    """
    __tablename__ = "documentos_empresa"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Empresa propietaria
    empresa_id = Column(
        UUID(as_uuid=True),
        ForeignKey("empresas.id", ondelete="CASCADE"),
        nullable=False
    )

    # Tipo de documento
    tipo = Column(
        SQLEnum(CompanyDocumentType, name="company_document_type_enum"),
        nullable=False
    )

    # Metadata del archivo
    nombre_archivo = Column(String(255), nullable=False)
    nombre_original = Column(String(255), nullable=False)
    extension = Column(String(10), nullable=False)
    mime_type = Column(String(100), nullable=False)
    tamano_bytes = Column(Integer, nullable=False)

    # Almacenamiento
    ruta_archivo = Column(Text, nullable=False)  # Path local o S3 key
    url_descarga = Column(Text, nullable=True)   # URL temporal de descarga

    # Estado de revision
    estado = Column(String(20), default="pendiente")  # pendiente, aprobado, rechazado
    revisado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    fecha_revision = Column(DateTime(timezone=True), nullable=True)
    motivo_rechazo = Column(Text, nullable=True)

    # Vigencia del documento
    fecha_emision = Column(Date, nullable=True)
    fecha_vencimiento = Column(Date, nullable=True)

    # Notas
    descripcion = Column(Text, nullable=True)
    notas = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    # Relaciones
    company = relationship("Company", back_populates="documentos")

    __table_args__ = (
        Index("idx_doc_empresa_empresa", "empresa_id"),
        Index("idx_doc_empresa_tipo", "tipo"),
        Index("idx_doc_empresa_estado", "estado"),
    )

    def __repr__(self):
        return f"<CompanyDocument {self.nombre_original} ({self.tipo})>"

    @property
    def esta_vigente(self) -> bool:
        """Verifica si el documento esta vigente."""
        if not self.fecha_vencimiento:
            return True
        return self.fecha_vencimiento >= datetime.now().date()
