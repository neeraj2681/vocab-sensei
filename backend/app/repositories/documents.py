from collections.abc import Sequence

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentWord


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, document_id: int) -> Document | None:
        return self._session.get(Document, document_id)

    def get_owned(self, document_id: int, owner_user_id: int) -> Document | None:
        document = self.get(document_id)
        return document if document and document.owner_user_id == owner_user_id else None

    def get_readable(self, document_id: int, user_id: int) -> Document | None:
        """The user's own book or a built-in classic."""
        document = self.get(document_id)
        if document and document.owner_user_id in (user_id, None):
            return document
        return None

    def list_classics(self) -> list[Document]:
        return list(
            self._session.scalars(
                select(Document).where(Document.owner_user_id.is_(None)).order_by(Document.id)
            )
        )

    def classic_by_filename(self, filename: str) -> Document | None:
        return self._session.scalars(
            select(Document).where(
                Document.owner_user_id.is_(None), Document.original_filename == filename
            )
        ).first()

    def list_owned(self, owner_user_id: int) -> list[Document]:
        return list(
            self._session.scalars(
                select(Document)
                .where(Document.owner_user_id == owner_user_id)
                .order_by(Document.uploaded_at.desc(), Document.id.desc())
            )
        )

    def add(self, document: Document) -> Document:
        self._session.add(document)
        self._session.flush()
        return document

    def delete(self, document: Document) -> None:
        self._session.delete(document)

    def word_counts(self, document_ids: Sequence[int]) -> dict[int, int]:
        """How many learnable words each document has; documents without words are left out."""
        rows = self._session.execute(
            select(DocumentWord.document_id, func.count())
            .where(DocumentWord.document_id.in_(document_ids))
            .group_by(DocumentWord.document_id)
        )
        return {document_id: count for document_id, count in rows}


def readable_by(user_id: int) -> ColumnElement[bool]:
    """SQL condition: a document the user may read (their own or a classic)."""
    return or_(Document.owner_user_id == user_id, Document.owner_user_id.is_(None))
