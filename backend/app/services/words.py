"""Stores a book's words: one shared `words` row per lemma, plus where each book uses it."""

from sqlalchemy.orm import Session

from app.core.enums import PartOfSpeech
from app.db.models import ChapterWord, Definition, Document, DocumentWord, Word
from app.dictionary.types import Dictionary
from app.extraction.words import Appearance, ExtractedWord
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
                    context_form=w.context_form,
                    pos=w.pos,
                )
                for w in defined
            ),
        )
        self.save_chapter_words(document, [(known[w.lemma].id, w) for w in defined])

    def reindex_chapters(self, document: Document, extracted: list[ExtractedWord]) -> None:
        """Records every chapter the book's existing words appear in; adds no new words."""
        ids = self._words.word_ids(document.id)
        self.save_chapter_words(document, [(ids[w.lemma], w) for w in extracted if w.lemma in ids])

    def save_chapter_words(
        self, document: Document, words: list[tuple[int, ExtractedWord]]
    ) -> None:
        """Replaces where each (word id, extracted word) appears chapter by chapter."""
        chapter_ids = {chapter.index: chapter.id for chapter in document.chapters}

        def row(word_id: int, item: ExtractedWord, appearance: Appearance) -> ChapterWord:
            return ChapterWord(
                chapter_id=chapter_ids[appearance.chapter_index],
                word_id=word_id,
                document_id=document.id,
                first_position=appearance.first_position,
                context_sentence=appearance.context_sentence,
                context_form=appearance.context_form,
                pos=item.pos,
            )

        self._words.replace_chapter_words(
            document.id,
            (row(word_id, item, a) for word_id, item in words for a in _appearances(item)),
        )

    def words_for_document(
        self, document: Document, chapter_index: int | None = None
    ) -> list[tuple[DocumentWord, Word, int, str | None]]:
        """(book row, word, chapter index, sentence) in reading order.

        For one chapter: every word it uses, even ones first seen earlier, with this chapter's
        sentence. For the whole book: each word once, where it first appears.
        """
        if chapter_index is None:
            return [
                (dw, w, chapter.index, dw.context_sentence)
                for dw, w, chapter in self._words.document_words(document.id)
            ]
        return [
            (dw, w, chapter_index, cw.context_sentence)
            for dw, cw, w in self._words.chapter_words(document.id, chapter_index)
        ]


def definitions_in_context(word: Word, pos: PartOfSpeech | None) -> list[Definition]:
    """The word's definitions, those for the part of speech the book uses first."""
    return sorted(word.definitions, key=lambda d: (d.pos != pos, d.sense_rank))


def _definitions(lemma: str, dictionary: Dictionary) -> list[Definition]:
    return [
        Definition(pos=s.pos, text=s.definition, source=dictionary.source, sense_rank=s.rank)
        for s in dictionary.senses(lemma)
    ]


def _appearances(item: ExtractedWord) -> tuple[Appearance, ...]:
    """Every chapter a word appears in; just its first appearance if nothing more was recorded."""
    return item.appearances or (
        Appearance(
            item.chapter_index, item.first_position, item.context_sentence, item.context_form
        ),
    )
