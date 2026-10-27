from collections.abc import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Chapter, DocumentWord, Word

_CHUNK = 500  # stay well under SQLite's limit on query parameters


class WordRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_lemmas(self, lemmas: Sequence[str]) -> dict[str, Word]:
        found: dict[str, Word] = {}
        for start in range(0, len(lemmas), _CHUNK):
            chunk = lemmas[start : start + _CHUNK]
            for word in self._session.scalars(select(Word).where(Word.lemma.in_(chunk))):
                found[word.lemma] = word
        return found

    def add_all(self, words: Iterable[Word]) -> None:
        self._session.add_all(words)
        self._session.flush()  # assigns ids

    def replace_document_words(self, document_id: int, rows: Iterable[DocumentWord]) -> None:
        self._session.execute(delete(DocumentWord).where(DocumentWord.document_id == document_id))
        self._session.add_all(rows)

    def document_words(
        self, document_id: int, chapter_index: int | None = None
    ) -> list[tuple[DocumentWord, Word, Chapter]]:
        query = (
            select(DocumentWord, Word, Chapter)
            .join(Word, Word.id == DocumentWord.word_id)
            .join(Chapter, Chapter.id == DocumentWord.chapter_id)
            .where(DocumentWord.document_id == document_id)
            .order_by(Chapter.index, DocumentWord.first_position)
        )
        if chapter_index is not None:
            query = query.where(Chapter.index == chapter_index)
        return [(dw, w, c) for dw, w, c in self._session.execute(query)]
