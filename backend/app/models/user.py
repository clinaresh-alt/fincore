"""
Modelo de Usuarios con soporte MFA y RBAC.
Separacion de credenciales y datos fiscales (IAM + KYC).
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime,
    Text, ForeignKey, Enum as SQLEnum, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    """Roles del sistema RBAC."""
    CLIENTE = "Cliente"
    INVERSIONISTA = "Inversionista"
    ANALISTA = "Analista"
    ADMIN = "Admin"


class PersonType(str, enum.Enum):
    """Tipo de persona fiscal."""
    FISICA = "Fisica"
    JURIDICA = "Juridica"


class User(Base):
    """
    Tabla de usuarios - Credenciales y acceso.
    Implementa MFA y control de intentos fallidos.
    """
    __tablename__ = "usuarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)

    # Rol y permisos (RBAC)
    rol = Column(
        SQLEnum(UserRole, name="user_role_enum"),
        default=UserRole.CLIENTE,
        nullable=False
    )

    # MFA (Google Authenticator)
    mfa_secret = Column(Text, nullable=True)
    mfa_enabled = Column(Boolean, default=False)

    # Verificaciones
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    phone_number = Column(String(20), nullable=True)

    # Control de acceso
    ultimo_login = Column(DateTime(timezone=True), nullable=True)
    intentos_fallidos = Column(Integer, default=0)
    bloqueado_hasta = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    # Relaciones
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    investments = relationship("Investment", back_populates="investor")
    documents = relationship(
        "Document",
        back_populates="user",
        primaryjoin="User.id==Document.user_id"
    )
    audit_logs = relationship("AuditLog", back_populates="user")
    companies = relationship("Company", back_populates="user", foreign_keys="Company.user_id")

    def __repr__(self):
        return f"<User {self.email}>"


class UserProfile(Base):
    """
    Perfil del cliente - Datos fiscales y KYC.
    Relacion 1:1 con User.
    """
    __tablename__ = "perfiles_clientes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )

    # Datos fiscales (cifrados en aplicacion)
    tax_id = Column(String(50), unique=True, nullable=False, index=True)  # RFC, CUIT, NIT
    tax_id_encrypted = Column(Text, nullable=True)  # Version cifrada AES-256
    nombre_legal = Column(String(255), nullable=False)

    # Tipo de persona
    tipo_persona = Column(
        SQLEnum(PersonType, name="person_type_enum"),
        nullable=False
    )

    # Direccion fiscal
    direccion_fiscal = Column(Text, nullable=True)
    ciudad = Column(String(100), nullable=True)
    estado_provincia = Column(String(100), nullable=True)
    codigo_postal = Column(String(20), nullable=True)
    pais = Column(String(100), default="Mexico")

    # Validacion tributaria
    situacion_tributaria = Column(JSON, nullable=True)  # Datos del SAT/AFIP
    fecha_validacion_tax = Column(DateTime(timezone=True), nullable=True)

    # KYC (Know Your Customer)
    verificado_kyc = Column(Boolean, default=False)
    kyc_score = Column(Integer, nullable=True)  # 0-100
    fecha_verificacion_kyc = Column(DateTime(timezone=True), nullable=True)

    # Datos bancarios (para depositos)
    cuenta_bancaria = Column(Text, nullable=True)  # Cifrado
    banco = Column(String(100), nullable=True)
    clabe = Column(Text, nullable=True)  # Cifrado

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow)

    # Relaciones
    user = relationship("User", back_populates="profile")

    def __repr__(self):
        return f"<UserProfile {self.nombre_legal}>"
