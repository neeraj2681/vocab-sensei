"""reminders by notification and email together

The single channel becomes two switches; each person keeps the channel they had.

Revision ID: 85d0bb8b8bd9
Revises: d50e8e6b4413
Create Date: 2026-11-02 19:13:54.337026

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types


# revision identifiers, used by Alembic.
revision: str = '85d0bb8b8bd9'
down_revision: Union[str, Sequence[str], None] = 'd50e8e6b4413'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('push', sa.Boolean(), server_default=sa.true(), nullable=False))
        batch_op.add_column(sa.Column('email', sa.Boolean(), server_default=sa.false(), nullable=False))
    reminders = sa.table(
        'reminders', sa.column('channel', sa.String()), sa.column('push', sa.Boolean()),
        sa.column('email', sa.Boolean()),
    )
    op.execute(reminders.update().values(
        push=reminders.c.channel == 'push', email=reminders.c.channel == 'email'
    ))
    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.drop_column('channel')


def downgrade() -> None:
    """Downgrade schema: one channel again (email if that was on, else notifications)."""
    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('channel', sa.VARCHAR(length=5), server_default='push', nullable=False))
    reminders = sa.table('reminders', sa.column('channel', sa.String()), sa.column('email', sa.Boolean()))
    op.execute(reminders.update().where(reminders.c.email == sa.true()).values(channel='email'))
    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.drop_column('email')
        batch_op.drop_column('push')
