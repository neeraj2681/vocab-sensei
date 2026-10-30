from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import WordStatus
from app.db.models import Chapter, DocumentWord, UserWord, Word


class LearningRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def new_words(
        self, user_id: int, document_id: int, from_chapter: int, limit: int
    ) -> list[tuple[DocumentWord, Word, Chapter]]:
        """A book's words the user hasn't started on, from `from_chapter` on, in reading order."""
        progress = and_(UserWord.word_id == DocumentWord.word_id, UserWord.user_id == user_id)
        query = (
            select(DocumentWord, Word, Chapter)
            .join(Word, Word.id == DocumentWord.word_id)
            .join(Chapter, Chapter.id == DocumentWord.chapter_id)
            .outerjoin(UserWord, progress)
            .where(
                DocumentWord.document_id == document_id,
                Chapter.index >= from_chapter,
                or_(UserWord.word_id.is_(None), UserWord.status == WordStatus.NEW),
            )
            .order_by(Chapter.index, DocumentWord.first_position)
            .limit(limit)
            .options(selectinload(Word.definitions))
        )
        return [(dw, w, c) for dw, w, c in self._session.execute(query)]
