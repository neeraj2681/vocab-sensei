"""Backing up and restoring a user's progress as one JSON file.

A backup holds progress, not books: every word's status and score, the full answer history (the
score graph and streak) and the current reads. Words are identified by lemma and books by title,
so a backup survives re-uploading books or moving to a new account. Restoring merges: progress
the account already has is kept, and answers already present aren't added twice.
"""

from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import DocumentStatus, QuestionType, WordStatus
from app.db.models import CurrentReading, Document, Question, QuizAnswer, UserWord, Word
from app.db.types import utcnow
from app.repositories.readings import ReadingRepository
from app.repositories.words import WordRepository

FORMAT_VERSION = 1
IMPORT_GENERATOR = "backup-import"  # marks the placeholder questions behind restored answers


class WordProgressItem(BaseModel):
    lemma: str = Field(min_length=1, max_length=100)
    status: WordStatus
    score: int = Field(ge=0)
    learned_at: datetime | None = None
    last_reviewed_at: datetime | None = None


class AnswerItem(BaseModel):
    lemma: str = Field(min_length=1, max_length=100)
    answered_at: datetime
    correct: bool
    knew_it: bool = False  # the "I know this" button rather than an answer
    points: int
    score_delta: int


class ReadingItem(BaseModel):
    title: str
    priority: int = Field(ge=0)
    chapter_index: int = Field(ge=0)


class Backup(BaseModel):
    version: int = FORMAT_VERSION
    exported_at: datetime
    words: list[WordProgressItem] = []
    answers: list[AnswerItem] = []
    readings: list[ReadingItem] = []


class RestoreSummary(BaseModel):
    words_added: int
    words_kept: int  # already had progress in this account
    answers_added: int
    answers_skipped: int  # already in this account
    readings_added: int
    books_missing: list[str]  # current reads whose book isn't uploaded (yet)


class BackupVersionError(Exception):
    pass


class BackupService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._words = WordRepository(session)
        self._readings = ReadingRepository(session)

    def export(self, user_id: int) -> Backup:
        progress = self._session.execute(
            select(UserWord, Word.lemma)
            .join(Word, Word.id == UserWord.word_id)
            .where(UserWord.user_id == user_id)
            .order_by(Word.lemma)
        )
        answers = self._session.execute(
            select(QuizAnswer, Word.lemma)
            .join(Word, Word.id == QuizAnswer.word_id)
            .where(QuizAnswer.user_id == user_id)
            .order_by(QuizAnswer.id)
        )
        return Backup(
            exported_at=utcnow(),
            words=[
                WordProgressItem(
                    lemma=lemma,
                    status=w.status,
                    score=w.score,
                    learned_at=w.learned_at,
                    last_reviewed_at=w.last_reviewed_at,
                )
                for w, lemma in progress
            ],
            answers=[
                AnswerItem(
                    lemma=lemma,
                    answered_at=a.answered_at,
                    correct=a.correct,
                    knew_it=a.chosen_index is None,
                    points=a.points,
                    score_delta=a.score_delta,
                )
                for a, lemma in answers
            ],
            readings=[
                ReadingItem(
                    title=r.document.title,
                    priority=r.priority,
                    chapter_index=r.current_chapter_index,
                )
                for r in self._readings.list_for(user_id)
            ],
        )

    def restore(self, user_id: int, backup: Backup) -> RestoreSummary:
        if backup.version != FORMAT_VERSION:
            raise BackupVersionError(f"This backup is version {backup.version}; expected 1")
        lemmas = sorted({w.lemma for w in backup.words} | {a.lemma for a in backup.answers})
        words = self._words.get_by_lemmas(lemmas)
        missing = [Word(lemma=lemma) for lemma in lemmas if lemma not in words]
        self._words.add_all(missing)  # definitions arrive when a book with the word is uploaded
        words.update({w.lemma: w for w in missing})

        existing = {
            uw.word_id
            for uw in self._session.scalars(select(UserWord).where(UserWord.user_id == user_id))
        }
        added = 0
        for item in backup.words:
            word_id = words[item.lemma].id
            if word_id in existing:
                continue
            existing.add(word_id)
            added += 1
            self._session.add(
                UserWord(
                    user_id=user_id,
                    word_id=word_id,
                    score=item.score,
                    status=item.status,
                    learned_at=item.learned_at,
                    last_reviewed_at=item.last_reviewed_at,
                )
            )

        answers_added, answers_skipped = self._restore_answers(user_id, backup.answers, words)
        readings_added, books_missing = self._restore_readings(user_id, backup.readings)
        self._session.commit()
        return RestoreSummary(
            words_added=added,
            words_kept=len(backup.words) - added,
            answers_added=answers_added,
            answers_skipped=answers_skipped,
            readings_added=readings_added,
            books_missing=books_missing,
        )

    def _restore_answers(
        self, user_id: int, answers: list[AnswerItem], words: dict[str, Word]
    ) -> tuple[int, int]:
        seen = {
            (word_id, answered_at)
            for word_id, answered_at in self._session.execute(
                select(QuizAnswer.word_id, QuizAnswer.answered_at).where(
                    QuizAnswer.user_id == user_id
                )
            )
        }
        added = 0
        for item in sorted(answers, key=lambda a: a.answered_at):  # keeps the graph in order
            word = words[item.lemma]
            if (word.id, item.answered_at) in seen:
                continue
            seen.add((word.id, item.answered_at))
            added += 1
            # Answers point at the question they answered; restored ones get a placeholder.
            question = Question(
                user_id=user_id,
                word_id=word.id,
                type=QuestionType.DEFINITION_MCQ,
                prompt=item.lemma,
                options=[],
                correct_index=0,
                generator=IMPORT_GENERATOR,
                created_at=item.answered_at,
            )
            self._session.add(question)
            self._session.flush()
            self._session.add(
                QuizAnswer(
                    user_id=user_id,
                    word_id=word.id,
                    question_id=question.id,
                    chosen_index=None if item.knew_it else (0 if item.correct else 1),
                    correct=item.correct,
                    score_delta=item.score_delta,
                    points=item.points,
                    answered_at=item.answered_at,
                )
            )
        return added, len(answers) - added

    def _restore_readings(self, user_id: int, readings: list[ReadingItem]) -> tuple[int, list[str]]:
        books = {
            d.title: d
            for d in self._session.scalars(
                select(Document).where(
                    Document.owner_user_id == user_id, Document.status == DocumentStatus.READY
                )
            )
        }
        current = {r.document_id for r in self._readings.list_for(user_id)}
        added = 0
        missing: list[str] = []
        for item in sorted(readings, key=lambda r: r.priority):
            book = books.get(item.title)
            if book is None:
                missing.append(item.title)
                continue
            if book.id in current:
                continue
            current.add(book.id)
            added += 1
            self._readings.add(
                CurrentReading(
                    user_id=user_id,
                    document_id=book.id,
                    priority=len(current) - 1,
                    current_chapter_index=min(item.chapter_index, max(len(book.chapters) - 1, 0)),
                )
            )
        return added, missing
