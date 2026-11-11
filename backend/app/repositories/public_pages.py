from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import DocumentStatus
from app.db.models import Chapter, ChapterWord, Document, Word


class PublicPagesRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _public(self) -> Select[Document]:
        return select(Document).where(
            Document.owner_user_id.is_(None),
            Document.status == DocumentStatus.READY,
            Document.slug.is_not(None),
        )

    def books(self) -> list[Document]:
        return list(self._session.scalars(self._public().order_by(Document.title, Document.id)))

    def book(self, slug: str) -> Document | None:
        query = self._public().where(Document.slug == slug).options(selectinload(Document.chapters))
        return self._session.scalars(query).one_or_none()

    def word_counts(self, document_id: int) -> dict[int, int]:
        """Chapter id -> number of words listed for it."""
        query = (
            select(ChapterWord.chapter_id, func.count())
            .where(ChapterWord.document_id == document_id)
            .group_by(ChapterWord.chapter_id)
        )
        return {chapter_id: count for chapter_id, count in self._session.execute(query)}

    def hardest(self, chapter: Chapter, limit: int) -> list[tuple[ChapterWord, Word]]:
        """The chapter's rarest words first (unknown frequency last), then alphabetical."""
        query = (
            select(ChapterWord, Word)
            .join(Word, Word.id == ChapterWord.word_id)
            .where(ChapterWord.chapter_id == chapter.id)
            .options(selectinload(Word.definitions))
            .order_by(Word.zipf_frequency.is_(None), Word.zipf_frequency, Word.lemma)
            .limit(limit)
        )
        return [(row[0], row[1]) for row in self._session.execute(query)]
