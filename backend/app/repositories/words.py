from collections.abc import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Chapter, ChapterWord, DocumentWord, Word

_CHUNK = 500  # stay well under SQLite's limit on query parameters


class WordRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_lemmas(self, lemmas: Sequence[str]) -> dict[str, Word]:
        """The stored words among `lemmas`, with their definitions loaded."""
        found: dict[str, Word] = {}
        for start in range(0, len(lemmas), _CHUNK):
            chunk = lemmas[start : start + _CHUNK]
            query = (
                select(Word).where(Word.lemma.in_(chunk)).options(selectinload(Word.definitions))
            )
            for word in self._session.scalars(query):
                found[word.lemma] = word
        return found

    def add_all(self, words: Iterable[Word]) -> None:
        self._session.add_all(words)
        self._session.flush()  # assigns ids

    def replace_document_words(self, document_id: int, rows: Iterable[DocumentWord]) -> None:
        self._session.execute(delete(DocumentWord).where(DocumentWord.document_id == document_id))
        self._session.add_all(rows)

    def replace_chapter_words(self, document_id: int, rows: Iterable[ChapterWord]) -> None:
        self._session.execute(delete(ChapterWord).where(ChapterWord.document_id == document_id))
        self._session.add_all(rows)

    def word_ids(self, document_id: int) -> dict[str, int]:
        """lemma -> word id for the words a book already has."""
        rows = self._session.execute(
            select(Word.lemma, Word.id)
            .join(DocumentWord, DocumentWord.word_id == Word.id)
            .where(DocumentWord.document_id == document_id)
        )
        return {lemma: word_id for lemma, word_id in rows}

    def document_words(self, document_id: int) -> list[tuple[DocumentWord, Word, Chapter]]:
        """Every word of the book, where it first appears, in reading order."""
        query = (
            select(DocumentWord, Word, Chapter)
            .join(Word, Word.id == DocumentWord.word_id)
            .join(Chapter, Chapter.id == DocumentWord.chapter_id)
            .where(DocumentWord.document_id == document_id)
            .order_by(Chapter.index, DocumentWord.first_position)
            .options(selectinload(Word.definitions))
        )
        return [(dw, w, c) for dw, w, c in self._session.execute(query)]

    def chapter_words(
        self, document_id: int, chapter_index: int
    ) -> list[tuple[DocumentWord, ChapterWord, Word]]:
        """Every word one chapter uses (even ones first seen earlier), in the chapter's order."""
        query = (
            select(DocumentWord, ChapterWord, Word)
            .join(
                DocumentWord,
                (DocumentWord.document_id == ChapterWord.document_id)
                & (DocumentWord.word_id == ChapterWord.word_id),
            )
            .join(Word, Word.id == ChapterWord.word_id)
            .join(Chapter, Chapter.id == ChapterWord.chapter_id)
            .where(ChapterWord.document_id == document_id, Chapter.index == chapter_index)
            .order_by(ChapterWord.first_position)
            .options(selectinload(Word.definitions))
        )
        return [(dw, cw, w) for dw, cw, w in self._session.execute(query)]
