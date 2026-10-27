"""conferencia de impedimentos do simples

Revision ID: e5b1c7a2f904
Revises: d2a9e47b1c30
Create Date: 2026-10-27 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b1c7a2f904'
down_revision: Union[str, Sequence[str], None] = 'd2a9e47b1c30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('clientes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('impedimentos_simples', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('clientes', schema=None) as batch_op:
        batch_op.drop_column('impedimentos_simples')
