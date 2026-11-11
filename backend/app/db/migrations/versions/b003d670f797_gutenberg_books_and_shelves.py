"""gutenberg books and shelves

Revision ID: b003d670f797
Revises: 5d5e67a0b59b
Create Date: 2026-11-11 20:53:31.015323

"""
import re
import unicodedata
from collections.abc import Iterable
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types


# revision identifiers, used by Alembic.
revision: str = 'b003d670f797'
down_revision: Union[str, Sequence[str], None] = '5d5e67a0b59b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Gutenberg books (shared, extracted once) and each reader's shelf of them. The built-in
    classics, found by their file name (gutenberg-<id>.epub), get their Gutenberg number and a
    public URL name (slug)."""
    op.create_table('shelf_books',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.Column('added_at', app.db.types.UTCDateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_shelf_books_document_id_documents'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_shelf_books_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'document_id', name=op.f('pk_shelf_books'))
    )
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gutenberg_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('slug', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('added_by_user_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_documents_added_by_user_id'), ['added_by_user_id'], unique=False)
        batch_op.create_unique_constraint(batch_op.f('uq_documents_gutenberg_id'), ['gutenberg_id'])
        batch_op.create_unique_constraint(batch_op.f('uq_documents_slug'), ['slug'])
        batch_op.create_foreign_key(batch_op.f('fk_documents_added_by_user_id_users'), 'users', ['added_by_user_id'], ['id'], ondelete='SET NULL')

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, title, original_filename FROM documents WHERE owner_user_id IS NULL")
    )
    updates = classic_ids_and_slugs(rows)
    if updates:
        conn.execute(
            sa.text("UPDATE documents SET gutenberg_id = :gutenberg_id, slug = :slug WHERE id = :id"),
            updates,
        )


def classic_ids_and_slugs(rows: Iterable[tuple[int, str, str]]) -> list[dict[str, object]]:
    """For books without an owner named gutenberg-<number>.epub: their Gutenberg number and a
    unique slug made from the title (same rules as app.core.slugs at the time of writing)."""
    found: list[dict[str, object]] = []
    taken: set[str] = set()
    for document_id, title, filename in rows:
        match = re.fullmatch(r"gutenberg-(\d+)\.epub", filename)
        if not match:
            continue
        base = _slugify(title)
        slug, n = base, 2
        while slug in taken:
            slug, n = f"{base}-{n}", n + 1
        taken.add(slug)
        found.append({"id": document_id, "gutenberg_id": int(match.group(1)), "slug": slug})
    return found


def _slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = ""
    for word in re.findall(r"[a-z0-9]+", ascii_text.lower().replace("'", "")):
        candidate = f"{slug}-{word}" if slug else word
        if len(candidate) > 80:
            break
        slug = candidate
    return slug or "book"


def downgrade() -> None:
    """Forgets Gutenberg numbers, slugs and shelves."""
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_documents_added_by_user_id_users'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('uq_documents_slug'), type_='unique')
        batch_op.drop_constraint(batch_op.f('uq_documents_gutenberg_id'), type_='unique')
        batch_op.drop_index(batch_op.f('ix_documents_added_by_user_id'))
        batch_op.drop_column('added_by_user_id')
        batch_op.drop_column('slug')
        batch_op.drop_column('gutenberg_id')

    op.drop_table('shelf_books')
