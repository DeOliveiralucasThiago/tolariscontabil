"""cnaes secundarios do cliente

Revision ID: c4d8f1a6b2e7
Revises: b7e1c5a2d9f3
Create Date: 2026-10-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d8f1a6b2e7'
down_revision: Union[str, Sequence[str], None] = 'b7e1c5a2d9f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('clientes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cnaes_secundarios', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('clientes', schema=None) as batch_op:
        batch_op.drop_column('cnaes_secundarios')
