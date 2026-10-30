"""never-ending quiz: questions per user, no rounds

Revision ID: 1510ffd184aa
Revises: 8ea01e54493a
Create Date: 2026-10-30 20:31:26.224168

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types


# revision identifiers, used by Alembic.
revision: str = '1510ffd184aa'
down_revision: Union[str, Sequence[str], None] = '8ea01e54493a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rounds are gone; nothing has been quizzed yet, and questions without a user can't be kept.
    op.execute("DELETE FROM quiz_answers")
    op.execute("DELETE FROM questions")

    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column('document_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_questions_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_questions_user_id_users'), 'users', ['user_id'], ['id'], ondelete='CASCADE')
        batch_op.create_foreign_key(batch_op.f('fk_questions_document_id_documents'), 'documents', ['document_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('quiz_answers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_quiz_answers_session_id'))
        batch_op.create_unique_constraint(batch_op.f('uq_quiz_answers_question_id'), ['question_id'])
        batch_op.drop_constraint(batch_op.f('fk_quiz_answers_session_id_quiz_sessions'), type_='foreignkey')
        batch_op.drop_column('session_id')

    with op.batch_alter_table('quiz_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_quiz_sessions_user_id'))
    op.drop_table('quiz_sessions')


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM quiz_answers")
    op.execute("DELETE FROM questions")

    op.create_table('quiz_sessions',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('user_id', sa.INTEGER(), nullable=False),
    sa.Column('started_at', sa.DATETIME(), nullable=False),
    sa.Column('finished_at', sa.DATETIME(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_quiz_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_quiz_sessions'))
    )
    with op.batch_alter_table('quiz_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_quiz_sessions_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('quiz_answers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session_id', sa.INTEGER(), nullable=False))
        batch_op.create_foreign_key(batch_op.f('fk_quiz_answers_session_id_quiz_sessions'), 'quiz_sessions', ['session_id'], ['id'], ondelete='CASCADE')
        batch_op.drop_constraint(batch_op.f('uq_quiz_answers_question_id'), type_='unique')
        batch_op.create_index(batch_op.f('ix_quiz_answers_session_id'), ['session_id'], unique=False)

    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_questions_document_id_documents'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_questions_user_id_users'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_questions_user_id'))
        batch_op.drop_column('document_id')
        batch_op.drop_column('user_id')
