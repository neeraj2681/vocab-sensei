"""Sorting a book's words before quizzing (docs/PROJECT_PLAN.md §5.1): Known / Unsure / New.

Known words are never quizzed, Unsure ones start at 50 and New ones at 0. Sorting is optional:
words nobody sorted are simply new. A choice can be changed or undone until the word has been
answered in the quiz; after that the quiz owns its score.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Chapter, ChapterWord, CurrentReading, Document, UserWord, Word
from app.quiz.learning_list import ahead_then_earlier
from app.repositories.learning import LearningRepository
from app.scoring.rules import Triage, initial_progress


class TriageError(Exception):
    pass


class NotInLibraryError(TriageError):
    pass


class AlreadyQuizzedError(TriageError):
    pass


@dataclass(frozen=True)
class UnsortedWord:
    word: Word
    occurrence: ChapterWord
    chapter: Chapter
    earlier: bool = False  # from a chapter before the one being read


@dataclass(frozen=True)
class SortBatch:
    remaining: int  # unsorted words in the whole book, including this batch
    from_chapter: int
    words: list[UnsortedWord]


class TriageService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repo = LearningRepository(session)

    def next_batch(
        self, user_id: int, document: Document, reading: CurrentReading | None, limit: int
    ) -> SortBatch:
        """Unsorted words in reading order from the chapter being read (or the first), with
        1 in 4 from the chapters before it."""
        start = reading.current_chapter_index if reading else 0

        def words(earlier: bool) -> list[UnsortedWord]:
            rows = self._repo.unsorted_words(user_id, document.id, start, limit, earlier=earlier)
            return [UnsortedWord(w, cw, c, earlier) for cw, w, c in rows]

        return SortBatch(
            remaining=self._repo.unsorted_count(user_id, document.id),
            from_chapter=start,
            words=ahead_then_earlier(words(False), words(True), limit, lambda u: u.word.id),
        )

    def sort(self, user_id: int, word_id: int, choice: Triage) -> UserWord:
        word = self._sortable(user_id, word_id)
        progress = initial_progress(choice, self._settings.scoring)
        if word is None:
            word = UserWord(user_id=user_id, word_id=word_id)
            self._repo.add(word)
        word.score, word.status, word.learned_at = progress.score, progress.status, None
        self._session.commit()
        return word

    def undo(self, user_id: int, word_id: int) -> None:
        """Back to unsorted."""
        word = self._sortable(user_id, word_id)
        if word is not None:
            self._repo.delete(word)
            self._session.commit()

    def _sortable(self, user_id: int, word_id: int) -> UserWord | None:
        if not self._repo.in_library(user_id, word_id):
            raise NotInLibraryError("None of your books has this word")
        if self._repo.was_quizzed(user_id, word_id):
            raise AlreadyQuizzedError("You've already answered this word in the quiz")
        return self._repo.user_word(user_id, word_id)
