"""add_custodial_wallet_fields

Revision ID: 45ff0a10d768
Revises: 20260225_001
Create Date: 2026-03-24 18:03:07.867882

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45ff0a10d768'
down_revision: Union[str, None] = '20260225_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agregar columnas para wallets custodiales
    op.add_column('user_wallets', sa.Column('encrypted_private_key', sa.Text(), nullable=True))
    op.add_column('user_wallets', sa.Column('is_custodial', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('user_wallets', 'is_custodial')
    op.drop_column('user_wallets', 'encrypted_private_key')
