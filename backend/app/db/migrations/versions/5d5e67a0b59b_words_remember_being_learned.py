"""words remember being learned

Revision ID: 5d5e67a0b59b
Revises: 812f072d92b8
Create Date: 2026-11-10 10:53:30.372332

"""
from collections.abc import Iterable
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types


# revision identifiers, used by Alembic.
revision: str = '5d5e67a0b59b'
down_revision: Union[str, Sequence[str], None] = '812f072d92b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Words remember being learned (a later miss costs more). Filled in from each word's answer
    history: replaying the score changes, a word counts once it reached 100 and stops once it fell
    to 50 or below. Learned words count; words at 50 or below don't, whatever the history says."""
    with op.batch_alter_table('user_words', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('was_learned', sa.Boolean(), server_default=sa.false(), nullable=False)
        )

    conn = op.get_bind()
    answers = conn.execute(
        sa.text("SELECT user_id, word_id, score_delta FROM quiz_answers ORDER BY id")
    )
    words = conn.execute(sa.text("SELECT user_id, word_id, status, score FROM user_words"))
    keys = learned_before(answers, words)
    if keys:
        conn.execute(
            sa.text(
                "UPDATE user_words SET was_learned = :yes "
                "WHERE user_id = :user_id AND word_id = :word_id"
            ).bindparams(yes=True),
            keys,
        )


def learned_before(
    answers: Iterable[tuple[int, int, int]], words: Iterable[tuple[int, int, str, int]]
) -> list[dict[str, int]]:
    """Which (user, word) count as learned before, from the answers' score changes (oldest first)
    and each word's current status and score."""
    replay: dict[tuple[int, int], tuple[int, bool]] = {}
    for user_id, word_id, delta in answers:
        score, learned = replay.get((user_id, word_id), (0, False))
        score = max(0, score + delta)
        if score >= 100:
            learned = True
        elif score <= 50:
            learned = False
        replay[(user_id, word_id)] = (score, learned)
    return [
        {"user_id": user_id, "word_id": word_id}
        for user_id, word_id, status, score in words
        if status == "learned" or (score > 50 and replay.get((user_id, word_id), (0, False))[1])
    ]


def downgrade() -> None:
    """Forgets which words were learned before."""
    with op.batch_alter_table('user_words', schema=None) as batch_op:
        batch_op.drop_column('was_learned')
