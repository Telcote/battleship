"""final contract

Revision ID: ea72f8b38507
Revises: 3f76080cb276
Create Date: 2026-09-12 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea72f8b38507'
down_revision: Union[str, None] = '3f76080cb276'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('game_sessions', 'dofirstshot')
    op.drop_column('game_sessions', 'close_reason')
    op.alter_column('shots', 'result', type_=sa.String(length=6))


def downgrade() -> None:
    op.alter_column('shots', 'result', type_=sa.String(length=4))
    op.add_column('game_sessions', sa.Column('close_reason', sa.String(length=32), nullable=True))
    op.add_column('game_sessions', sa.Column('dofirstshot', sa.Boolean(), nullable=True))
