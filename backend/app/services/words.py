"""Stores a book's words: one shared `words` row per lemma, plus where each book uses it."""

from sqlalchemy.orm import Session

from app.db.models import Document, DocumentWord, Word
from app.extraction.words import ExtractedWord
from app.repositories.words import WordRepository


class WordService:
    def __init__(self, session: Session) -> None:
        self._words = WordRepository(session)

    def save_for_document(self, document: Document, extracted: list[ExtractedWord]) -> None:
        """Replaces the document's word list. Does not commit; the caller owns the transaction."""
        known = self._words.get_by_lemmas([w.lemma for w in extracted])
        new = [
            Word(lemma=w.lemma, zipf_frequency=w.zipf) for w in extracted if w.lemma not in known
        ]
        self._words.add_all(new)
        known.update({w.lemma: w for w in new})

        chapter_ids = {chapter.index: chapter.id for chapter in document.chapters}
        self._words.replace_document_words(
            document.id,
            (
                DocumentWord(
                    document_id=document.id,
                    word_id=known[w.lemma].id,
                    chapter_id=chapter_ids[w.chapter_index],
                    first_position=w.first_position,
                    occurrences=w.occurrences,
                    context_sentence=w.context_sentence,
                )
                for w in extracted
            ),
        )

    def words_for_document(
        self, document: Document, chapter_index: int | None = None
    ) -> list[tuple[DocumentWord, Word, int]]:
        """(occurrence, word, chapter index) in reading order."""
        return [
            (dw, w, chapter.index)
            for dw, w, chapter in self._words.document_words(document.id, chapter_index)
        ]
