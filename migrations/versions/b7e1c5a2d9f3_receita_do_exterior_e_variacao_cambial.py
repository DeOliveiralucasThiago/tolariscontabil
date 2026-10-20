"""receita do exterior e variação cambial nos dados contábeis mensais

Revision ID: b7e1c5a2d9f3
Revises: 97578bc2ddd2
Create Date: 2026-10-20 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7e1c5a2d9f3'
down_revision: Union[str, Sequence[str], None] = '97578bc2ddd2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('financeiro_mensal') as lote:
        lote.add_column(sa.Column('receita_exterior_centavos', sa.BigInteger(), nullable=True))
        lote.add_column(sa.Column('variacao_cambial_centavos', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('financeiro_mensal') as lote:
        lote.drop_column('variacao_cambial_centavos')
        lote.drop_column('receita_exterior_centavos')
