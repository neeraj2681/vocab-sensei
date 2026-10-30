"""Stores a book's words: one shared `words` row per lemma, plus where each book uses it."""

from sqlalchemy.orm import Session

from app.core.enums import PartOfSpeech
from app.db.models import Definition, Document, DocumentWord, Word
from app.dictionary.types import Dictionary
from app.extraction.words import ExtractedWord
from app.repositories.words import WordRepository


class WordService:
    def __init__(self, session: Session) -> None:
        self._words = WordRepository(session)

    def save_for_document(
        self, document: Document, extracted: list[ExtractedWord], dictionary: Dictionary
    ) -> None:
        """Replaces the document's word list. Does not commit; the caller owns the transaction.

        Words the dictionary doesn't know are left out: without a definition they can't be quizzed,
        and they're mostly names, archaic spellings and leftovers of bad lemmatisation.
        """
        known = self._words.get_by_lemmas([w.lemma for w in extracted])
        new: list[Word] = []
        for item in extracted:
            word = known.get(item.lemma)
            if word is None:
                word = known[item.lemma] = Word(lemma=item.lemma, zipf_frequency=item.zipf)
                new.append(word)
            if not word.definitions:  # a new word, or one stored before it could be looked up
                word.definitions = _definitions(word.lemma, dictionary)
        self._words.add_all(w for w in new if w.definitions)
        defined = [item for item in extracted if known[item.lemma].definitions]

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
                    pos=w.pos,
                )
                for w in defined
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


def definitions_in_context(word: Word, pos: PartOfSpeech | None) -> list[Definition]:
    """The word's definitions, those for the part of speech the book uses first."""
    return sorted(word.definitions, key=lambda d: (d.pos != pos, d.sense_rank))


def _definitions(lemma: str, dictionary: Dictionary) -> list[Definition]:
    return [
        Definition(pos=s.pos, text=s.definition, source=dictionary.source, sense_rank=s.rank)
        for s in dictionary.senses(lemma)
    ]
