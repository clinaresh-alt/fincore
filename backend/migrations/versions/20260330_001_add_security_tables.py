"""Add security tables for Phase 1

Revision ID: 20260330_001
Revises:
Create Date: 2026-03-30

Tables added:
- withdrawal_whitelist: Whitelist de direcciones de retiro con cuarentena 24h
- user_devices: Dispositivos registrados del usuario
- user_sessions: Sesiones activas
- password_history: Historial de contraseñas
- account_freezes: Congelamiento de cuenta
- anti_phishing_phrases: Frase anti-phishing
- mfa_backup_codes: Códigos de respaldo MFA
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260330_001'
down_revision = None  # Ajustar al último revision ID
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Crear enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE withdrawal_address_type_enum AS ENUM (
                'crypto_erc20', 'crypto_trc20', 'bank_clabe', 'bank_iban', 'bank_ach'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE whitelist_status_enum AS ENUM (
                'pending', 'active', 'suspended', 'cancelled'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE device_status_enum AS ENUM (
                'trusted', 'unknown', 'suspicious', 'blocked'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE account_freeze_reason_enum AS ENUM (
                'user_requested', 'suspicious', 'compliance', 'fraud', 'failed_login'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Tabla user_devices (primero porque es referenciada por otras)
    op.create_table(
        'user_devices',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('device_fingerprint', sa.String(64), nullable=False),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('browser_name', sa.String(50), nullable=True),
        sa.Column('browser_version', sa.String(20), nullable=True),
        sa.Column('os_name', sa.String(50), nullable=True),
        sa.Column('os_version', sa.String(20), nullable=True),
        sa.Column('device_type', sa.String(20), nullable=True),
        sa.Column('last_ip', postgresql.INET, nullable=True),
        sa.Column('last_country', sa.String(2), nullable=True),
        sa.Column('last_city', sa.String(100), nullable=True),
        sa.Column('last_region', sa.String(100), nullable=True),
        sa.Column('is_vpn', sa.Boolean, default=False),
        sa.Column('is_tor', sa.Boolean, default=False),
        sa.Column('is_proxy', sa.Boolean, default=False),
        sa.Column('risk_score', sa.Integer, default=0),
        sa.Column('status', sa.Enum('trusted', 'unknown', 'suspicious', 'blocked', name='device_status_enum', create_type=False), default='unknown'),
        sa.Column('device_name', sa.String(100), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('login_count', sa.Integer, default=0),
        sa.Column('notification_sent', sa.Boolean, default=False),
        sa.Column('trusted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_device_user_fingerprint', 'user_devices', ['user_id', 'device_fingerprint'])
    op.create_index('ix_device_status', 'user_devices', ['status'])
    op.create_index('ix_device_last_seen', 'user_devices', ['last_seen_at'])

    # Tabla withdrawal_whitelist
    op.create_table(
        'withdrawal_whitelist',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('address_type', sa.Enum('crypto_erc20', 'crypto_trc20', 'bank_clabe', 'bank_iban', 'bank_ach', name='withdrawal_address_type_enum', create_type=False), nullable=False),
        sa.Column('address', sa.String(255), nullable=False),
        sa.Column('address_hash', sa.String(64), nullable=False),
        sa.Column('metadata', postgresql.JSONB, default={}),
        sa.Column('label', sa.String(100), nullable=True),
        sa.Column('status', sa.Enum('pending', 'active', 'suspended', 'cancelled', name='whitelist_status_enum', create_type=False), default='pending'),
        sa.Column('quarantine_ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cancellation_token', sa.String(64), unique=True, nullable=True),
        sa.Column('cancellation_token_expires', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notification_email_sent', sa.Boolean, default=False),
        sa.Column('notification_push_sent', sa.Boolean, default=False),
        sa.Column('notification_sms_sent', sa.Boolean, default=False),
        sa.Column('is_primary', sa.Boolean, default=False),
        sa.Column('times_used', sa.Integer, default=0),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_withdrawn', sa.String(50), default='0'),
        sa.Column('added_from_ip', postgresql.INET, nullable=True),
        sa.Column('added_from_device_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('user_devices.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_whitelist_user_status', 'withdrawal_whitelist', ['user_id', 'status'])
    op.create_index('ix_whitelist_quarantine', 'withdrawal_whitelist', ['quarantine_ends_at'])
    op.create_index('ix_whitelist_address_hash', 'withdrawal_whitelist', ['address_hash'])
    op.create_unique_constraint('uq_whitelist_user_address', 'withdrawal_whitelist', ['user_id', 'address_hash'])

    # Tabla user_sessions
    op.create_table(
        'user_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('user_devices.id', ondelete='SET NULL'), nullable=True),
        sa.Column('session_token_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('refresh_token_hash', sa.String(64), nullable=True),
        sa.Column('ip_address', postgresql.INET, nullable=True),
        sa.Column('country', sa.String(2), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_current', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_session_user_active', 'user_sessions', ['user_id', 'is_active'])
    op.create_index('ix_session_expires', 'user_sessions', ['expires_at'])

    # Tabla password_history
    op.create_table(
        'password_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('password_hash', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_password_history_user', 'password_history', ['user_id', 'created_at'])

    # Tabla account_freezes
    op.create_table(
        'account_freezes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reason', sa.Enum('user_requested', 'suspicious', 'compliance', 'fraud', 'failed_login', name='account_freeze_reason_enum', create_type=False), nullable=False),
        sa.Column('reason_details', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('unfreeze_token', sa.String(64), unique=True, nullable=True),
        sa.Column('unfreeze_token_expires', sa.DateTime(timezone=True), nullable=True),
        sa.Column('frozen_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('unfrozen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('frozen_from_ip', postgresql.INET, nullable=True),
        sa.Column('unfrozen_from_ip', postgresql.INET, nullable=True),
        sa.Column('unfrozen_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
    )
    op.create_index('ix_freeze_user_active', 'account_freezes', ['user_id', 'is_active'])

    # Tabla anti_phishing_phrases
    op.create_table(
        'anti_phishing_phrases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('phrase_encrypted', sa.Text, nullable=False),
        sa.Column('phrase_hint', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Tabla mfa_backup_codes
    op.create_table(
        'mfa_backup_codes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code_hash', sa.String(64), nullable=False),
        sa.Column('is_used', sa.Boolean, default=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('used_from_ip', postgresql.INET, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_backup_code_user', 'mfa_backup_codes', ['user_id', 'is_used'])

    # Agregar nuevos valores al enum audit_action_enum
    op.execute("""
        ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'WHITELIST_ADDRESS_ADDED';
        ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'WHITELIST_ADDRESS_REMOVED';
        ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'WHITELIST_ADDRESS_USED';
        ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'ANTI_PHISHING_CONFIGURED';
        ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'MFA_BACKUP_CODES_GENERATED';
        ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'MFA_BACKUP_CODE_USED';
        ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'ACCOUNT_FROZEN';
        ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'ACCOUNT_UNFROZEN';
        ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'NEW_DEVICE_DETECTED';
        ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'DEVICE_TRUSTED';
        ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'DEVICE_BLOCKED';
        ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'SESSION_REVOKED';
        ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'ALL_SESSIONS_REVOKED';
        ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'PASSWORD_HIBP_CHECK';
    """)


def downgrade() -> None:
    op.drop_table('mfa_backup_codes')
    op.drop_table('anti_phishing_phrases')
    op.drop_table('account_freezes')
    op.drop_table('password_history')
    op.drop_table('user_sessions')
    op.drop_table('withdrawal_whitelist')
    op.drop_table('user_devices')

    op.execute('DROP TYPE IF EXISTS withdrawal_address_type_enum')
    op.execute('DROP TYPE IF EXISTS whitelist_status_enum')
    op.execute('DROP TYPE IF EXISTS device_status_enum')
    op.execute('DROP TYPE IF EXISTS account_freeze_reason_enum')
