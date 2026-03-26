"""Add bank account tables for fiat integration

Revision ID: 20260325_002
Revises: 20260325_001_add_remittance_tables
Create Date: 2026-03-25

Tablas:
- bank_accounts: Cuentas bancarias (operativas y de usuarios)
- bank_transactions: Transacciones bancarias (SPEI-IN/OUT)
- bank_statement_imports: Importación de estados de cuenta
- virtual_clabe_assignments: Asignación de CLABEs virtuales
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers
revision = '20260325_002'
down_revision = '20260325_001'
branch_labels = None
depends_on = None


def upgrade():
    # Crear enums primero
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE bank_provider_enum AS ENUM (
                'stp', 'spei_directo', 'banxico', 'arcus', 'conekta', 'openpay', 'stripe', 'wise'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE bank_account_type_enum AS ENUM (
                'clabe', 'cuenta', 'tarjeta', 'iban', 'swift', 'ach', 'virtual'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE bank_account_status_enum AS ENUM (
                'pending_verification', 'active', 'suspended', 'closed', 'blocked'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE bank_transaction_type_enum AS ENUM (
                'deposit', 'withdrawal', 'transfer_in', 'transfer_out', 'fee', 'interest', 'reversal', 'adjustment'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE bank_transaction_status_enum AS ENUM (
                'pending', 'processing', 'completed', 'failed', 'cancelled', 'reversed', 'returned'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE spei_operation_type_enum AS ENUM (
                'ordinario', 'terceros', 'tef', 'ccen'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Tabla bank_accounts
    op.create_table(
        'bank_accounts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('account_alias', sa.String(100), unique=True, nullable=False),
        sa.Column('owner_id', UUID(as_uuid=True), sa.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_platform_account', sa.Boolean, default=False),
        sa.Column('bank_name', sa.String(100), nullable=False),
        sa.Column('bank_code', sa.String(10), nullable=True),
        sa.Column('account_type', sa.Enum('clabe', 'cuenta', 'tarjeta', 'iban', 'swift', 'ach', 'virtual', name='bank_account_type_enum', create_type=False), nullable=False),
        sa.Column('account_number', sa.String(50), nullable=False),
        sa.Column('account_number_masked', sa.String(50), nullable=True),
        sa.Column('clabe', sa.String(18), nullable=True, index=True),
        sa.Column('swift_bic', sa.String(11), nullable=True),
        sa.Column('iban', sa.String(34), nullable=True),
        sa.Column('routing_number', sa.String(20), nullable=True),
        sa.Column('currency', sa.String(3), nullable=False, default='MXN'),
        sa.Column('holder_name', sa.String(200), nullable=False),
        sa.Column('holder_rfc', sa.String(13), nullable=True),
        sa.Column('holder_curp', sa.String(18), nullable=True),
        sa.Column('provider', sa.Enum('stp', 'spei_directo', 'banxico', 'arcus', 'conekta', 'openpay', 'stripe', 'wise', name='bank_provider_enum', create_type=False), nullable=True),
        sa.Column('provider_account_id', sa.String(100), nullable=True),
        sa.Column('status', sa.Enum('pending_verification', 'active', 'suspended', 'closed', 'blocked', name='bank_account_status_enum', create_type=False), default='pending_verification', nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_known_balance', sa.Numeric(18, 2), default=0),
        sa.Column('balance_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('daily_limit', sa.Numeric(18, 2), nullable=True),
        sa.Column('monthly_limit', sa.Numeric(18, 2), nullable=True),
        sa.Column('extra_data', JSONB, default={}),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_bank_accounts_owner', 'bank_accounts', ['owner_id'])
    op.create_index('ix_bank_accounts_status', 'bank_accounts', ['status'])
    op.create_index('ix_bank_accounts_platform', 'bank_accounts', ['is_platform_account'])

    # Tabla bank_transactions
    op.create_table(
        'bank_transactions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('account_id', UUID(as_uuid=True), sa.ForeignKey('bank_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reference_id', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('bank_reference', sa.String(100), nullable=True, index=True),
        sa.Column('tracking_key', sa.String(30), nullable=True, index=True),
        sa.Column('transaction_type', sa.Enum('deposit', 'withdrawal', 'transfer_in', 'transfer_out', 'fee', 'interest', 'reversal', 'adjustment', name='bank_transaction_type_enum', create_type=False), nullable=False),
        sa.Column('amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, default='MXN'),
        sa.Column('balance_after', sa.Numeric(18, 2), nullable=True),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', 'cancelled', 'reversed', 'returned', name='bank_transaction_status_enum', create_type=False), default='pending', nullable=False),
        sa.Column('counterparty_name', sa.String(200), nullable=True),
        sa.Column('counterparty_bank', sa.String(100), nullable=True),
        sa.Column('counterparty_account', sa.String(50), nullable=True),
        sa.Column('counterparty_clabe', sa.String(18), nullable=True),
        sa.Column('counterparty_rfc', sa.String(13), nullable=True),
        sa.Column('concept', sa.String(500), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('remittance_id', UUID(as_uuid=True), sa.ForeignKey('remittances.id', ondelete='SET NULL'), nullable=True),
        sa.Column('spei_operation_type', sa.Enum('ordinario', 'terceros', 'tef', 'ccen', name='spei_operation_type_enum', create_type=False), nullable=True),
        sa.Column('provider', sa.Enum('stp', 'spei_directo', 'banxico', 'arcus', 'conekta', 'openpay', 'stripe', 'wise', name='bank_provider_enum', create_type=False), nullable=True),
        sa.Column('provider_transaction_id', sa.String(100), nullable=True),
        sa.Column('transaction_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('value_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fee_amount', sa.Numeric(18, 2), default=0),
        sa.Column('error_code', sa.String(20), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('raw_data', JSONB, default={}),
        sa.Column('extra_data', JSONB, default={}),
        sa.Column('reconciled', sa.Boolean, default=False),
        sa.Column('reconciled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reconciliation_log_id', UUID(as_uuid=True), sa.ForeignKey('reconciliation_logs.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_bank_tx_account', 'bank_transactions', ['account_id'])
    op.create_index('ix_bank_tx_date', 'bank_transactions', ['transaction_date'])
    op.create_index('ix_bank_tx_status', 'bank_transactions', ['status'])
    op.create_index('ix_bank_tx_type', 'bank_transactions', ['transaction_type'])
    op.create_index('ix_bank_tx_remittance', 'bank_transactions', ['remittance_id'])
    op.create_index('ix_bank_tx_reconciled', 'bank_transactions', ['reconciled'])

    # Tabla bank_statement_imports
    op.create_table(
        'bank_statement_imports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('account_id', UUID(as_uuid=True), sa.ForeignKey('bank_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_type', sa.String(20), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_records', sa.Integer, default=0),
        sa.Column('records_imported', sa.Integer, default=0),
        sa.Column('records_duplicated', sa.Integer, default=0),
        sa.Column('records_failed', sa.Integer, default=0),
        sa.Column('total_debits', sa.Numeric(18, 2), default=0),
        sa.Column('total_credits', sa.Numeric(18, 2), default=0),
        sa.Column('opening_balance', sa.Numeric(18, 2), nullable=True),
        sa.Column('closing_balance', sa.Numeric(18, 2), nullable=True),
        sa.Column('import_status', sa.String(20), default='pending'),
        sa.Column('error_log', JSONB, default=[]),
        sa.Column('imported_by', UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index('ix_statement_import_account', 'bank_statement_imports', ['account_id'])
    op.create_index('ix_statement_import_period', 'bank_statement_imports', ['period_start', 'period_end'])

    # Tabla virtual_clabe_assignments
    op.create_table(
        'virtual_clabe_assignments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('virtual_clabe', sa.String(18), unique=True, nullable=False, index=True),
        sa.Column('assignment_type', sa.String(20), nullable=False),
        sa.Column('remittance_id', UUID(as_uuid=True), sa.ForeignKey('remittances.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True),
        sa.Column('base_account_id', UUID(as_uuid=True), sa.ForeignKey('bank_accounts.id'), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('times_used', sa.Integer, default=0),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_received', sa.Numeric(18, 2), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index('ix_virtual_clabe_assignment', 'virtual_clabe_assignments', ['assignment_type', 'remittance_id', 'user_id'])
    op.create_index('ix_virtual_clabe_active', 'virtual_clabe_assignments', ['is_active'])


def downgrade():
    op.drop_table('virtual_clabe_assignments')
    op.drop_table('bank_statement_imports')
    op.drop_table('bank_transactions')
    op.drop_table('bank_accounts')

    # Eliminar enums
    op.execute('DROP TYPE IF EXISTS spei_operation_type_enum')
    op.execute('DROP TYPE IF EXISTS bank_transaction_status_enum')
    op.execute('DROP TYPE IF EXISTS bank_transaction_type_enum')
    op.execute('DROP TYPE IF EXISTS bank_account_status_enum')
    op.execute('DROP TYPE IF EXISTS bank_account_type_enum')
    op.execute('DROP TYPE IF EXISTS bank_provider_enum')
