"""The learning list: new words from the user's current reads, in the order they'll be learned.

Per book: from the current chapter onward (earlier chapters are left out), in reading order,
skipping words already in progress, learned or known. Books share the list by priority
(see app.quiz.learning_list).
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Chapter, Document, DocumentWord, Word
from app.quiz.learning_list import mix_by_priority
from app.repositories.learning import LearningRepository
from app.repositories.readings import ReadingRepository


@dataclass(frozen=True)
class LearningWord:
    word: Word
    occurrence: DocumentWord  # where the book first uses it
    document: Document
    chapter: Chapter


class LearningService:
    def __init__(self, session: Session) -> None:
        self._learning = LearningRepository(session)
        self._readings = ReadingRepository(session)

    def next_new_words(self, user_id: int, count: int) -> list[LearningWord]:
        queues = [
            [
                LearningWord(
                    word=word, occurrence=occurrence, document=reading.document, chapter=chapter
                )
                for occurrence, word, chapter in self._learning.new_words(
                    user_id,
                    reading.document_id,
                    reading.current_chapter_index,
                    # Words shared with other books may be dropped as duplicates; at most `count`
                    # are, so twice as many always leaves enough.
                    limit=2 * count,
                )
            ]
            for reading in self._readings.list_for(user_id)
        ]
        return mix_by_priority(queues, count, key=lambda item: item.word.id)
