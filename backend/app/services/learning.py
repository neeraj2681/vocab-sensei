"""The learning list: new words from the user's current reads, in the order they'll be learned.

Per book, in reading order and skipping words already in progress, learned or known: mostly words
from the current chapter on (each at the next chapter that uses it), with 1 in 4 from the chapters
before it. Books share the list by priority (see app.quiz.learning_list).
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Chapter, ChapterWord, CurrentReading, Document, Word
from app.quiz.learning_list import ahead_then_earlier, mix_by_priority
from app.repositories.learning import LearningRepository
from app.repositories.readings import ReadingRepository


@dataclass(frozen=True)
class LearningWord:
    word: Word
    occurrence: ChapterWord  # where the reader meets it next (or first, for earlier chapters)
    document: Document
    chapter: Chapter
    earlier: bool = False  # from a chapter before the one being read


class LearningService:
    def __init__(self, session: Session) -> None:
        self._learning = LearningRepository(session)
        self._readings = ReadingRepository(session)

    def next_new_words(self, user_id: int, count: int) -> list[LearningWord]:
        # Words shared with other books may be dropped as duplicates; at most `count` are, so
        # twice as many always leaves enough.
        limit = 2 * count
        queues = []
        for reading in self._readings.list_for(user_id):

            def words(earlier: bool, reading: CurrentReading = reading) -> list[LearningWord]:
                rows = self._learning.new_words(
                    user_id,
                    reading.document_id,
                    reading.current_chapter_index,
                    limit,
                    earlier=earlier,
                )
                return [
                    LearningWord(
                        word=word,
                        occurrence=occurrence,
                        document=reading.document,
                        chapter=chapter,
                        earlier=earlier,
                    )
                    for occurrence, word, chapter in rows
                ]

            queues.append(ahead_then_earlier(words(False), words(True), limit, _word_id))
        return mix_by_priority(queues, count, key=_word_id)


def _word_id(item: LearningWord) -> int:
    return item.word.id
