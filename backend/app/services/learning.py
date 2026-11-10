"""The learning list: new words from the user's current reads, in the order they'll be learned.

Per book, skipping words already in progress, learned or known: first the words of the chapters
being read (the reader chooses them; by default the current chapter and the next two), then the
rest of the book from the first of them, in reading order (each word at the next chapter that uses
it), with 1 in 4 from the chapters before it. Books take turns (see app.quiz.learning_list).
"""

from collections.abc import Collection, Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Chapter, ChapterWord, CurrentReading, Document, User, Word
from app.quiz.learning_list import ahead_then_earlier, mix_by_priority, reading_chapters
from app.quiz.placement import easy_above
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
        self._session = session
        self._learning = LearningRepository(session)
        self._readings = ReadingRepository(session)

    def easy_above(self, user_id: int) -> float:
        """Words more common than this are probably known to the user (from their level, or the
        default cutoff while they have none)."""
        user = self._session.get(User, user_id)
        return easy_above(user.vocab_level if user else None)

    def next_new_words(
        self, user_id: int, count: int, only: Collection[int] | None = None
    ) -> list[LearningWord]:
        """The next `count` new words, from every current read or only the books in `only`."""
        # Words shared with other books may be dropped as duplicates; at most `count` are, so
        # twice as many always leaves enough.
        limit = 2 * count
        max_zipf = self.easy_above(user_id)  # probably known words don't come in
        queues = []
        for reading in self._readings.list_for(user_id):
            if only is not None and reading.document_id not in only:
                continue

            chosen = reading_chapters(
                reading.chapters, reading.current_chapter_index, len(reading.document.chapters)
            )

            def items(
                rows: Iterable[tuple[ChapterWord, Word, Chapter]],
                earlier: bool = False,
                reading: CurrentReading = reading,
            ) -> list[LearningWord]:
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

            def words(
                earlier: bool, reading: CurrentReading = reading, chosen: list[int] = chosen
            ) -> list[LearningWord]:
                # The chosen chapters' words first, then the book on from the first of them.
                if earlier:
                    return items(
                        self._learning.new_words(
                            user_id,
                            reading.document_id,
                            chosen[0],
                            limit,
                            earlier=True,
                            max_zipf=max_zipf,
                        ),
                        earlier=True,
                    )
                first = [
                    item
                    for index in chosen
                    for item in items(
                        self._learning.new_words_in_chapter(
                            user_id, reading.document_id, index, limit, max_zipf
                        )
                    )
                ]
                rest = items(
                    self._learning.new_words(
                        user_id, reading.document_id, chosen[0], limit, max_zipf=max_zipf
                    )
                )
                return first + rest

            queues.append(ahead_then_earlier(words(False), words(True), limit, _word_id))
        return mix_by_priority(queues, count, key=_word_id)


def _word_id(item: LearningWord) -> int:
    return item.word.id
