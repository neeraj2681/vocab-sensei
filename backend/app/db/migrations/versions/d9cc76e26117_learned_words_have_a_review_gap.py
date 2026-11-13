"""learned words have a review gap

Revision ID: d9cc76e26117
Revises: 1d8a9dd161fa
Create Date: 2026-11-13 21:08:18.266640

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types


# revision identifiers, used by Alembic.
revision: str = 'd9cc76e26117'
down_revision: Union[str, Sequence[str], None] = '1d8a9dd161fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCORES_TO_GAPS = (
    "UPDATE user_words SET interval_weeks = CASE WHEN 1 + (score - 100) / 5 > 16 THEN 16 "
    "ELSE 1 + (score - 100) / 5 END, score = 100 WHERE score > 100"
)


def upgrade() -> None:
    """Learned words get a gap between reviews (1 week to start). Scores above 100 came from
    reviews that kept adding 10: each 5 points over 100 bought a week before the word was due
    again, so they become that gap (105 -> 2 weeks, 115 -> 4, at most 16) and the score is 100."""
    with op.batch_alter_table('user_words', schema=None) as batch_op:
        batch_op.add_column(sa.Column('interval_weeks', sa.Integer(), server_default='1', nullable=False))
    op.execute(SCORES_TO_GAPS)


def downgrade() -> None:
    """Forgets the gaps (scores stay at 100)."""
    with op.batch_alter_table('user_words', schema=None) as batch_op:
        batch_op.drop_column('interval_weeks')
