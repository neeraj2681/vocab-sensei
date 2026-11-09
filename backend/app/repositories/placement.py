from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.enums import WordStatus
from app.db.models import CurrentReading, Document, DocumentWord, QuizAnswer, UserWord, Word


class PlacementRepository:
    """What the placement check and a reader's level are worked out from."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def first_answers(self, user_id: int) -> list[tuple[float, bool]]:
        """(Zipf, answered right) for the first real answer to each word, oldest first."""
        rows = self._session.execute(
            select(QuizAnswer.word_id, QuizAnswer.correct, Word.zipf_frequency)
            .join(Word, Word.id == QuizAnswer.word_id)
            .where(
                QuizAnswer.user_id == user_id,
                QuizAnswer.chosen_index.is_not(None),
                Word.zipf_frequency.is_not(None),
            )
            .order_by(QuizAnswer.id)
        )
        seen: set[int] = set()
        first: list[tuple[float, bool]] = []
        for word_id, correct, zipf in rows:
            if word_id not in seen and zipf is not None:
                seen.add(word_id)
                first.append((zipf, bool(correct)))
        return first

    def known_zipfs(self, user_id: int) -> list[float]:
        """Zipf of each word the user marked as already known."""
        return list(
            self._session.scalars(
                select(Word.zipf_frequency)
                .join(UserWord, UserWord.word_id == Word.id)
                .where(
                    UserWord.user_id == user_id,
                    UserWord.status == WordStatus.KNOWN,
                    Word.zipf_frequency.is_not(None),
                )
            )
        )

    def probably_known(self, user_id: int, above: float, limit: int) -> list[tuple[Word, str]]:
        """Words in the user's current reads, not started, more common than `above`: (word, book
        title), most common first."""
        progress = and_(UserWord.word_id == Word.id, UserWord.user_id == user_id)
        rows = self._session.execute(
            select(Word, Document.title)
            .join(DocumentWord, DocumentWord.word_id == Word.id)
            .join(Document, Document.id == DocumentWord.document_id)
            .join(
                CurrentReading,
                and_(
                    CurrentReading.document_id == Document.id,
                    CurrentReading.user_id == user_id,
                ),
            )
            .outerjoin(UserWord, progress)
            .where(
                Word.zipf_frequency > above,
                or_(UserWord.word_id.is_(None), UserWord.status == WordStatus.NEW),
            )
            .order_by(Word.zipf_frequency.desc(), Word.lemma, CurrentReading.priority)
        )
        seen: set[int] = set()
        found: list[tuple[Word, str]] = []
        for word, title in rows:
            if word.id not in seen:
                seen.add(word.id)
                found.append((word, title))
                if len(found) >= limit:
                    break
        return found
