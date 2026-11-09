"""leaderboard hidden by default

Revision ID: e353eff74b13
Revises: 485e6ec26910
Create Date: 2026-11-09 09:29:20.070505

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types


# revision identifiers, used by Alembic.
revision: str = 'e353eff74b13'
down_revision: Union[str, Sequence[str], None] = '485e6ec26910'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Off the leaderboard unless chosen in Settings, for new and existing accounts alike."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('show_on_leaderboard', server_default=sa.false())
    op.execute(sa.text("UPDATE users SET show_on_leaderboard = :off").bindparams(off=False))


def downgrade() -> None:
    """Only the default goes back; everyone stays hidden until they choose."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('show_on_leaderboard', server_default=sa.true())
