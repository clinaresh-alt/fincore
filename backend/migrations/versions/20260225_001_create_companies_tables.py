"""
Crear tablas de empresas y documentos de empresa.

Revision ID: 20260225_001
Revises:
Create Date: 2026-02-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260225_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crear enums
    company_type_enum = postgresql.ENUM(
        'Persona Fisica', 'Persona Moral', 'S.A.', 'S.A. de C.V.',
        'S. de R.L.', 'S. de R.L. de C.V.', 'S.A.P.I.', 'S.A.P.I. de C.V.',
        'A.C.', 'S.C.', 'Fideicomiso', 'Otro',
        name='company_type_enum',
        create_type=False
    )

    company_size_enum = postgresql.ENUM(
        'Micro', 'Pequena', 'Mediana', 'Grande',
        name='company_size_enum',
        create_type=False
    )

    company_status_enum = postgresql.ENUM(
        'Pendiente', 'En Revision', 'Verificada', 'Activa', 'Suspendida', 'Rechazada',
        name='company_status_enum',
        create_type=False
    )

    company_document_type_enum = postgresql.ENUM(
        'Acta Constitutiva', 'Constancia de Situacion Fiscal RFC', 'Poder Notarial del Representante',
        'INE del Representante Legal', 'Comprobante de Domicilio Fiscal', 'Estados Financieros Auditados',
        'Declaracion Anual de Impuestos', 'Opinion de Cumplimiento SAT', 'Cedula de Identificacion Fiscal',
        'Contrato Social', 'Acta de Asamblea', 'Curriculum Empresarial', 'Cartera de Clientes',
        'Certificaciones y Licencias', 'Otro Documento',
        name='company_document_type_enum',
        create_type=False
    )

    # Crear los tipos ENUM primero
    op.execute("CREATE TYPE company_type_enum AS ENUM ('Persona Fisica', 'Persona Moral', 'S.A.', 'S.A. de C.V.', 'S. de R.L.', 'S. de R.L. de C.V.', 'S.A.P.I.', 'S.A.P.I. de C.V.', 'A.C.', 'S.C.', 'Fideicomiso', 'Otro')")
    op.execute("CREATE TYPE company_size_enum AS ENUM ('Micro', 'Pequena', 'Mediana', 'Grande')")
    op.execute("CREATE TYPE company_status_enum AS ENUM ('Pendiente', 'En Revision', 'Verificada', 'Activa', 'Suspendida', 'Rechazada')")
    op.execute("CREATE TYPE company_document_type_enum AS ENUM ('Acta Constitutiva', 'Constancia de Situacion Fiscal RFC', 'Poder Notarial del Representante', 'INE del Representante Legal', 'Comprobante de Domicilio Fiscal', 'Estados Financieros Auditados', 'Declaracion Anual de Impuestos', 'Opinion de Cumplimiento SAT', 'Cedula de Identificacion Fiscal', 'Contrato Social', 'Acta de Asamblea', 'Curriculum Empresarial', 'Cartera de Clientes', 'Certificaciones y Licencias', 'Otro Documento')")

    # Crear tabla empresas
    op.create_table(
        'empresas',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Datos Basicos
        sa.Column('razon_social', sa.String(255), nullable=False),
        sa.Column('nombre_comercial', sa.String(255), nullable=True),
        sa.Column('tipo_empresa', sa.Enum('Persona Fisica', 'Persona Moral', 'S.A.', 'S.A. de C.V.', 'S. de R.L.', 'S. de R.L. de C.V.', 'S.A.P.I.', 'S.A.P.I. de C.V.', 'A.C.', 'S.C.', 'Fideicomiso', 'Otro', name='company_type_enum', create_type=False), server_default='Persona Moral'),
        sa.Column('rfc', sa.String(13), nullable=False, unique=True),
        sa.Column('curp', sa.String(18), nullable=True),

        # Datos Fiscales
        sa.Column('regimen_fiscal', sa.String(100), nullable=True),
        sa.Column('actividad_economica', sa.String(255), nullable=True),
        sa.Column('clave_actividad_sat', sa.String(10), nullable=True),
        sa.Column('fecha_constitucion', sa.Date(), nullable=True),
        sa.Column('numero_escritura', sa.String(50), nullable=True),
        sa.Column('notaria', sa.String(255), nullable=True),
        sa.Column('fecha_inscripcion_rpc', sa.Date(), nullable=True),

        # Direccion Fiscal
        sa.Column('calle', sa.String(255), nullable=True),
        sa.Column('numero_exterior', sa.String(20), nullable=True),
        sa.Column('numero_interior', sa.String(20), nullable=True),
        sa.Column('colonia', sa.String(100), nullable=True),
        sa.Column('codigo_postal', sa.String(5), nullable=True),
        sa.Column('municipio', sa.String(100), nullable=True),
        sa.Column('estado', sa.String(100), nullable=True),
        sa.Column('pais', sa.String(100), server_default='Mexico'),

        # Contacto
        sa.Column('telefono_principal', sa.String(20), nullable=True),
        sa.Column('telefono_secundario', sa.String(20), nullable=True),
        sa.Column('email_corporativo', sa.String(255), nullable=True),
        sa.Column('sitio_web', sa.String(255), nullable=True),

        # Representante Legal
        sa.Column('representante_nombre', sa.String(255), nullable=True),
        sa.Column('representante_cargo', sa.String(100), nullable=True),
        sa.Column('representante_email', sa.String(255), nullable=True),
        sa.Column('representante_telefono', sa.String(20), nullable=True),
        sa.Column('representante_rfc', sa.String(13), nullable=True),
        sa.Column('representante_curp', sa.String(18), nullable=True),

        # Informacion Financiera
        sa.Column('tamano_empresa', sa.Enum('Micro', 'Pequena', 'Mediana', 'Grande', name='company_size_enum', create_type=False), nullable=True),
        sa.Column('numero_empleados', sa.Integer(), nullable=True),
        sa.Column('ingresos_anuales', sa.Numeric(18, 2), nullable=True),
        sa.Column('capital_social', sa.Numeric(18, 2), nullable=True),
        sa.Column('antiguedad_anos', sa.Integer(), nullable=True),

        # Sector e Industria
        sa.Column('sector', sa.String(100), nullable=True),
        sa.Column('industria', sa.String(100), nullable=True),
        sa.Column('giro', sa.String(255), nullable=True),

        # Informacion Bancaria
        sa.Column('banco', sa.String(100), nullable=True),
        sa.Column('cuenta_clabe', sa.String(18), nullable=True),
        sa.Column('cuenta_numero', sa.String(20), nullable=True),

        # Estado y Verificacion
        sa.Column('estado_verificacion', sa.Enum('Pendiente', 'En Revision', 'Verificada', 'Activa', 'Suspendida', 'Rechazada', name='company_status_enum', create_type=False), server_default='Pendiente'),
        sa.Column('fecha_verificacion', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verificado_por', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('notas_verificacion', sa.Text(), nullable=True),
        sa.Column('score_riesgo', sa.Integer(), nullable=True),

        # Metadata
        sa.Column('datos_adicionales', postgresql.JSONB(), nullable=True),

        # Usuario propietario
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Crear indices para empresas
    op.create_index('idx_empresa_rfc', 'empresas', ['rfc'])
    op.create_index('idx_empresa_razon_social', 'empresas', ['razon_social'])
    op.create_index('idx_empresa_estado', 'empresas', ['estado_verificacion'])
    op.create_index('idx_empresa_user', 'empresas', ['user_id'])

    # Crear tabla documentos_empresa
    op.create_table(
        'documentos_empresa',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Empresa propietaria
        sa.Column('empresa_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('empresas.id', ondelete='CASCADE'), nullable=False),

        # Tipo de documento
        sa.Column('tipo', sa.Enum(
            'Acta Constitutiva', 'Constancia de Situacion Fiscal RFC', 'Poder Notarial del Representante',
            'INE del Representante Legal', 'Comprobante de Domicilio Fiscal', 'Estados Financieros Auditados',
            'Declaracion Anual de Impuestos', 'Opinion de Cumplimiento SAT', 'Cedula de Identificacion Fiscal',
            'Contrato Social', 'Acta de Asamblea', 'Curriculum Empresarial', 'Cartera de Clientes',
            'Certificaciones y Licencias', 'Otro Documento',
            name='company_document_type_enum', create_type=False
        ), nullable=False),

        # Metadata del archivo
        sa.Column('nombre_archivo', sa.String(255), nullable=False),
        sa.Column('nombre_original', sa.String(255), nullable=False),
        sa.Column('extension', sa.String(10), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('tamano_bytes', sa.Integer(), nullable=False),

        # Almacenamiento
        sa.Column('ruta_archivo', sa.Text(), nullable=False),
        sa.Column('url_descarga', sa.Text(), nullable=True),

        # Estado de revision
        sa.Column('estado', sa.String(20), server_default='pendiente'),
        sa.Column('revisado_por', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('fecha_revision', sa.DateTime(timezone=True), nullable=True),
        sa.Column('motivo_rechazo', sa.Text(), nullable=True),

        # Vigencia del documento
        sa.Column('fecha_emision', sa.Date(), nullable=True),
        sa.Column('fecha_vencimiento', sa.Date(), nullable=True),

        # Notas
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('notas', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Crear indices para documentos
    op.create_index('idx_doc_empresa_empresa', 'documentos_empresa', ['empresa_id'])
    op.create_index('idx_doc_empresa_tipo', 'documentos_empresa', ['tipo'])
    op.create_index('idx_doc_empresa_estado', 'documentos_empresa', ['estado'])

    # Agregar columna empresa_id a proyectos si no existe
    op.add_column('proyectos', sa.Column('empresa_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_proyecto_empresa',
        'proyectos', 'empresas',
        ['empresa_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Eliminar FK de proyectos
    op.drop_constraint('fk_proyecto_empresa', 'proyectos', type_='foreignkey')
    op.drop_column('proyectos', 'empresa_id')

    # Eliminar indices de documentos
    op.drop_index('idx_doc_empresa_empresa', table_name='documentos_empresa')
    op.drop_index('idx_doc_empresa_tipo', table_name='documentos_empresa')
    op.drop_index('idx_doc_empresa_estado', table_name='documentos_empresa')

    # Eliminar tabla documentos_empresa
    op.drop_table('documentos_empresa')

    # Eliminar indices de empresas
    op.drop_index('idx_empresa_rfc', table_name='empresas')
    op.drop_index('idx_empresa_razon_social', table_name='empresas')
    op.drop_index('idx_empresa_estado', table_name='empresas')
    op.drop_index('idx_empresa_user', table_name='empresas')

    # Eliminar tabla empresas
    op.drop_table('empresas')

    # Eliminar tipos ENUM
    op.execute('DROP TYPE IF EXISTS company_document_type_enum')
    op.execute('DROP TYPE IF EXISTS company_status_enum')
    op.execute('DROP TYPE IF EXISTS company_size_enum')
    op.execute('DROP TYPE IF EXISTS company_type_enum')
