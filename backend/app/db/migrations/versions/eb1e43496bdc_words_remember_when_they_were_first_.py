"""words remember when they were first learned

Revision ID: eb1e43496bdc
Revises: d9cc76e26117
Create Date: 2026-11-13 21:45:30.263835

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types


# revision identifiers, used by Alembic.
revision: str = 'eb1e43496bdc'
down_revision: Union[str, Sequence[str], None] = 'd9cc76e26117'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Words learned (now, or at some point) count as first learned when we last saw them learned.
FIRST_LEARNED = (
    "UPDATE user_words SET first_learned_at = COALESCE(learned_at, last_reviewed_at) "
    "WHERE first_learned_at IS NULL AND (status = 'learned' OR was_learned = :yes)"
)


def upgrade() -> None:
    """Words remember when they were first learned (reviews never change it), so only first-time
    learns count for quests, recaps and the leaderboard. Filled in for words that are learned or
    were learned: their learned time, else their last review."""
    with op.batch_alter_table('user_words', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('first_learned_at', app.db.types.UTCDateTime(timezone=True), nullable=True)
        )
    op.get_bind().execute(sa.text(FIRST_LEARNED).bindparams(yes=True))


def downgrade() -> None:
    """Forgets when words were first learned."""
    with op.batch_alter_table('user_words', schema=None) as batch_op:
        batch_op.drop_column('first_learned_at')
