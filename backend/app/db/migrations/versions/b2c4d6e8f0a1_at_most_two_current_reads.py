"""at most two current reads

Revision ID: b2c4d6e8f0a1
Revises: dcd606ec050f
Create Date: 2026-11-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b2c4d6e8f0a1'
down_revision: Union[str, Sequence[str], None] = 'dcd606ec050f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keeps each user's top two books; the rest go back to My books (word progress is kept)."""
    op.execute("DELETE FROM current_readings WHERE priority >= 2")


def downgrade() -> None:
    """The removed reads can't be told apart from books never started, so nothing comes back."""
