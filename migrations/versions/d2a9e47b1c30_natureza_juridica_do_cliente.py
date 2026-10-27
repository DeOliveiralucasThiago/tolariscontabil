"""natureza juridica do cliente

Revision ID: d2a9e47b1c30
Revises: c4d8f1a6b2e7
Create Date: 2026-10-27 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2a9e47b1c30'
down_revision: Union[str, Sequence[str], None] = 'c4d8f1a6b2e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('clientes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('natureza_juridica', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('natureza_juridica_codigo', sa.String(length=4), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('clientes', schema=None) as batch_op:
        batch_op.drop_column('natureza_juridica_codigo')
        batch_op.drop_column('natureza_juridica')
