from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, document_id: int) -> Document | None:
        return self._session.get(Document, document_id)

    def get_owned(self, document_id: int, owner_user_id: int) -> Document | None:
        document = self.get(document_id)
        return document if document and document.owner_user_id == owner_user_id else None

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
