"""Add remittance tables

Revision ID: 20260325_001
Revises: a6a113351299
Create Date: 2026-03-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260325_001'
down_revision: Union[str, None] = 'a6a113351299'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums
    remittance_status_enum = postgresql.ENUM(
        'initiated', 'pending_deposit', 'deposited', 'locked', 'processing',
        'disbursed', 'completed', 'refund_pending', 'refunded', 'failed',
        'cancelled', 'expired',
        name='remittance_status_enum',
        create_type=False
    )

    blockchain_remittance_status_enum = postgresql.ENUM(
        'pending', 'submitted', 'mined', 'confirmed', 'reverted', 'replaced',
        name='blockchain_remittance_status_enum',
        create_type=False
    )

    payment_method_enum = postgresql.ENUM(
        'spei', 'wire_transfer', 'card', 'cash', 'crypto',
        name='payment_method_enum',
        create_type=False
    )

    disbursement_method_enum = postgresql.ENUM(
        'bank_transfer', 'mobile_wallet', 'cash_pickup', 'home_delivery',
        name='disbursement_method_enum',
        create_type=False
    )

    stablecoin_enum = postgresql.ENUM(
        'USDC', 'USDT', 'DAI',
        name='stablecoin_enum',
        create_type=False
    )

    # Create enum types
    op.execute("CREATE TYPE remittance_status_enum AS ENUM ('initiated', 'pending_deposit', 'deposited', 'locked', 'processing', 'disbursed', 'completed', 'refund_pending', 'refunded', 'failed', 'cancelled', 'expired')")
    op.execute("CREATE TYPE blockchain_remittance_status_enum AS ENUM ('pending', 'submitted', 'mined', 'confirmed', 'reverted', 'replaced')")
    op.execute("CREATE TYPE payment_method_enum AS ENUM ('spei', 'wire_transfer', 'card', 'cash', 'crypto')")
    op.execute("CREATE TYPE disbursement_method_enum AS ENUM ('bank_transfer', 'mobile_wallet', 'cash_pickup', 'home_delivery')")
    op.execute("CREATE TYPE stablecoin_enum AS ENUM ('USDC', 'USDT', 'DAI')")

    # Create remittances table
    op.create_table(
        'remittances',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('reference_code', sa.String(20), unique=True, nullable=False, index=True),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True),
        sa.Column('recipient_info', postgresql.JSONB, nullable=False),
        sa.Column('amount_fiat_source', sa.Numeric(18, 2), nullable=False),
        sa.Column('currency_source', sa.String(3), nullable=False),
        sa.Column('amount_fiat_destination', sa.Numeric(18, 2), nullable=True),
        sa.Column('currency_destination', sa.String(3), nullable=False),
        sa.Column('amount_stablecoin', sa.Numeric(18, 6), nullable=True),
        sa.Column('stablecoin', stablecoin_enum, server_default='USDC'),
        sa.Column('exchange_rate_source_usd', sa.Numeric(18, 8), nullable=True),
        sa.Column('exchange_rate_usd_destination', sa.Numeric(18, 8), nullable=True),
        sa.Column('exchange_rate_locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('platform_fee', sa.Numeric(18, 2), server_default='0'),
        sa.Column('network_fee', sa.Numeric(18, 6), server_default='0'),
        sa.Column('total_fees', sa.Numeric(18, 2), server_default='0'),
        sa.Column('status', remittance_status_enum, server_default='initiated', nullable=False, index=True),
        sa.Column('payment_method', payment_method_enum, nullable=True),
        sa.Column('disbursement_method', disbursement_method_enum, nullable=True),
        sa.Column('escrow_locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('escrow_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('sender_ip', sa.String(45), nullable=True),
        sa.Column('sender_device_fingerprint', sa.String(255), nullable=True),
        sa.CheckConstraint('amount_fiat_source > 0', name='check_positive_amount'),
    )

    # Create indexes for remittances
    op.create_index('ix_remittances_sender_status', 'remittances', ['sender_id', 'status'])
    op.create_index('ix_remittances_created_at', 'remittances', ['created_at'])
    op.create_index('ix_remittances_escrow_expires', 'remittances', ['escrow_expires_at'])

    # Create remittance_blockchain_txs table
    op.create_table(
        'remittance_blockchain_txs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('remittance_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('remittances.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tx_hash', sa.String(66), unique=True, nullable=True, index=True),
        sa.Column('operation', sa.String(50), nullable=False),
        sa.Column('blockchain_status', blockchain_remittance_status_enum, server_default='pending', nullable=False),
        sa.Column('network', sa.String(50), nullable=False, server_default='polygon'),
        sa.Column('contract_address', sa.String(42), nullable=True),
        sa.Column('from_address', sa.String(42), nullable=True),
        sa.Column('to_address', sa.String(42), nullable=True),
        sa.Column('value_wei', sa.Numeric(38, 0), server_default='0'),
        sa.Column('gas_limit', sa.Integer, nullable=True),
        sa.Column('gas_used', sa.Integer, nullable=True),
        sa.Column('gas_price_gwei', sa.Numeric(18, 9), nullable=True),
        sa.Column('nonce', sa.Integer, nullable=True),
        sa.Column('block_number', sa.Integer, nullable=True),
        sa.Column('block_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmations', sa.Integer, server_default='0'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('retry_count', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create indexes for blockchain txs
    op.create_index('ix_remittance_tx_status', 'remittance_blockchain_txs', ['remittance_id', 'blockchain_status'])
    op.create_index('ix_remittance_tx_hash', 'remittance_blockchain_txs', ['tx_hash'])

    # Create reconciliation_logs table
    op.create_table(
        'reconciliation_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('check_timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expected_balance_ledger', sa.Numeric(18, 6), nullable=False),
        sa.Column('actual_balance_ledger', sa.Numeric(18, 6), nullable=False),
        sa.Column('expected_balance_onchain', sa.Numeric(18, 6), nullable=False),
        sa.Column('actual_balance_onchain', sa.Numeric(18, 6), nullable=False),
        sa.Column('expected_balance_fiat', sa.Numeric(18, 2), nullable=True),
        sa.Column('actual_balance_fiat', sa.Numeric(18, 2), nullable=True),
        sa.Column('discrepancy_ledger', sa.Numeric(18, 6), server_default='0'),
        sa.Column('discrepancy_onchain', sa.Numeric(18, 6), server_default='0'),
        sa.Column('discrepancy_fiat', sa.Numeric(18, 2), server_default='0'),
        sa.Column('discrepancy_detected', sa.Boolean, server_default='false'),
        sa.Column('network', sa.String(50), nullable=False, server_default='polygon'),
        sa.Column('stablecoin', sa.String(10), nullable=False, server_default='USDC'),
        sa.Column('contract_address', sa.String(42), nullable=True),
        sa.Column('error_payload', postgresql.JSONB, server_default='{}'),
        sa.Column('action_taken', sa.Text, nullable=True),
        sa.Column('resolved', sa.Boolean, server_default='false'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('usuarios.id'), nullable=True),
    )

    # Create indexes for reconciliation
    op.create_index('ix_reconciliation_timestamp', 'reconciliation_logs', ['check_timestamp'])
    op.create_index('ix_reconciliation_discrepancy', 'reconciliation_logs', ['discrepancy_detected'])

    # Create remittance_limits table
    op.create_table(
        'remittance_limits',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('corridor_source', sa.String(3), nullable=False),
        sa.Column('corridor_destination', sa.String(3), nullable=False),
        sa.Column('kyc_level', sa.Integer, nullable=False),
        sa.Column('min_amount_usd', sa.Numeric(18, 2), server_default='10'),
        sa.Column('max_amount_usd', sa.Numeric(18, 2), server_default='1000'),
        sa.Column('daily_limit_usd', sa.Numeric(18, 2), server_default='1000'),
        sa.Column('monthly_limit_usd', sa.Numeric(18, 2), server_default='5000'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create index for limits
    op.create_index('ix_limits_corridor', 'remittance_limits', ['corridor_source', 'corridor_destination', 'kyc_level'])

    # Create exchange_rate_history table
    op.create_table(
        'exchange_rate_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('currency_from', sa.String(3), nullable=False),
        sa.Column('currency_to', sa.String(3), nullable=False),
        sa.Column('rate', sa.Numeric(18, 8), nullable=False),
        sa.Column('rate_source', sa.String(50), nullable=False),
        sa.Column('captured_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create index for exchange rate
    op.create_index('ix_exchange_rate_currencies', 'exchange_rate_history', ['currency_from', 'currency_to', 'captured_at'])

    # Insert default remittance limits for common corridors
    op.execute("""
        INSERT INTO remittance_limits (id, corridor_source, corridor_destination, kyc_level, min_amount_usd, max_amount_usd, daily_limit_usd, monthly_limit_usd)
        VALUES
        -- USD -> MXN (KYC levels 0-3)
        (gen_random_uuid(), 'USD', 'MXN', 0, 10, 500, 500, 1500),
        (gen_random_uuid(), 'USD', 'MXN', 1, 10, 1000, 1000, 5000),
        (gen_random_uuid(), 'USD', 'MXN', 2, 10, 5000, 5000, 25000),
        (gen_random_uuid(), 'USD', 'MXN', 3, 10, 10000, 10000, 100000),
        -- USD -> CLP
        (gen_random_uuid(), 'USD', 'CLP', 0, 10, 500, 500, 1500),
        (gen_random_uuid(), 'USD', 'CLP', 1, 10, 1000, 1000, 5000),
        (gen_random_uuid(), 'USD', 'CLP', 2, 10, 5000, 5000, 25000),
        (gen_random_uuid(), 'USD', 'CLP', 3, 10, 10000, 10000, 100000),
        -- MXN -> USD
        (gen_random_uuid(), 'MXN', 'USD', 0, 200, 10000, 10000, 30000),
        (gen_random_uuid(), 'MXN', 'USD', 1, 200, 20000, 20000, 100000),
        (gen_random_uuid(), 'MXN', 'USD', 2, 200, 100000, 100000, 500000),
        (gen_random_uuid(), 'MXN', 'USD', 3, 200, 200000, 200000, 2000000)
    """)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('ix_exchange_rate_currencies', table_name='exchange_rate_history')
    op.drop_table('exchange_rate_history')

    op.drop_index('ix_limits_corridor', table_name='remittance_limits')
    op.drop_table('remittance_limits')

    op.drop_index('ix_reconciliation_discrepancy', table_name='reconciliation_logs')
    op.drop_index('ix_reconciliation_timestamp', table_name='reconciliation_logs')
    op.drop_table('reconciliation_logs')

    op.drop_index('ix_remittance_tx_hash', table_name='remittance_blockchain_txs')
    op.drop_index('ix_remittance_tx_status', table_name='remittance_blockchain_txs')
    op.drop_table('remittance_blockchain_txs')

    op.drop_index('ix_remittances_escrow_expires', table_name='remittances')
    op.drop_index('ix_remittances_created_at', table_name='remittances')
    op.drop_index('ix_remittances_sender_status', table_name='remittances')
    op.drop_table('remittances')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS stablecoin_enum")
    op.execute("DROP TYPE IF EXISTS disbursement_method_enum")
    op.execute("DROP TYPE IF EXISTS payment_method_enum")
    op.execute("DROP TYPE IF EXISTS blockchain_remittance_status_enum")
    op.execute("DROP TYPE IF EXISTS remittance_status_enum")
