"""word rows remember the meaning used

Revision ID: 1d8a9dd161fa
Revises: b003d670f797
Create Date: 2026-11-11 21:08:50.759700

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types


# revision identifiers, used by Alembic.
revision: str = '1d8a9dd161fa'
down_revision: Union[str, Sequence[str], None] = 'b003d670f797'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Each place a book uses a word can name the meaning used there."""
    with op.batch_alter_table('chapter_words', schema=None) as batch_op:
        batch_op.add_column(sa.Column('meaning_rank', sa.Integer(), nullable=True))

    with op.batch_alter_table('document_words', schema=None) as batch_op:
        batch_op.add_column(sa.Column('meaning_rank', sa.Integer(), nullable=True))



def downgrade() -> None:
    """Forgets the meanings."""
    with op.batch_alter_table('document_words', schema=None) as batch_op:
        batch_op.drop_column('meaning_rank')

    with op.batch_alter_table('chapter_words', schema=None) as batch_op:
        batch_op.drop_column('meaning_rank')
