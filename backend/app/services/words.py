"""Stores a book's words: one shared `words` row per lemma, plus where each book uses it."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.enums import PartOfSpeech
from app.db.models import ChapterWord, Definition, Document, DocumentWord, Word
from app.dictionary.senses import best_sense
from app.dictionary.types import Dictionary, Sense
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
        Each lemma is looked up in the dictionary at most once per call.
        """
        senses_of: dict[str, list[Sense]] = {}

        def senses(lemma: str) -> list[Sense]:
            if lemma not in senses_of:
                senses_of[lemma] = dictionary.senses(lemma)
            return senses_of[lemma]

        known = self._words.get_by_lemmas([w.lemma for w in extracted])
        new: list[Word] = []
        for item in extracted:
            word = known.get(item.lemma)
            if word is None:
                word = known[item.lemma] = Word(lemma=item.lemma, zipf_frequency=item.zipf)
                new.append(word)
            if not word.definitions:  # a new word, or one stored before it could be looked up
                word.definitions = _definitions(senses(word.lemma), dictionary.source)
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
                    meaning_rank=_meaning_rank(w.lemma, w.pos, w.context_sentence, senses(w.lemma)),
                )
                for w in defined
            ),
        )
        self.save_chapter_words(document, [(known[w.lemma].id, w) for w in defined], senses)

    def reindex_chapters(self, document: Document, extracted: list[ExtractedWord]) -> None:
        """Records every chapter the book's existing words appear in; adds no new words."""
        ids = self._words.word_ids(document.id)
        self.save_chapter_words(document, [(ids[w.lemma], w) for w in extracted if w.lemma in ids])

    def save_chapter_words(
        self,
        document: Document,
        words: list[tuple[int, ExtractedWord]],
        senses: Callable[[str], list[Sense]] | None = None,
    ) -> None:
        """Replaces where each (word id, extracted word) appears chapter by chapter.

        With `senses` (the dictionary's senses for a lemma), each appearance also records the
        meaning its sentence uses; without it, no meaning is recorded.
        """
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
                meaning_rank=(
                    None
                    if senses is None
                    else _meaning_rank(
                        item.lemma, item.pos, appearance.context_sentence, senses(item.lemma)
                    )
                ),
            )

        self._words.replace_chapter_words(
            document.id,
            (row(word_id, item, a) for word_id, item in words for a in _appearances(item)),
        )

    def words_for_document(
        self, document: Document, chapter_index: int | None = None
    ) -> list[tuple[DocumentWord, Word, int, str | None, int | None]]:
        """(book row, word, chapter index, sentence, meaning rank) in reading order.

        For one chapter: every word it uses, even ones first seen earlier, with this chapter's
        sentence and the meaning rank of that sentence (from the chapter's row). For the whole
        book: each word once, where it first appears, with that sentence and its meaning rank.
        """
        if chapter_index is None:
            return [
                (dw, w, chapter.index, dw.context_sentence, dw.meaning_rank)
                for dw, w, chapter in self._words.document_words(document.id)
            ]
        return [
            (dw, w, chapter_index, cw.context_sentence, cw.meaning_rank)
            for dw, cw, w in self._words.chapter_words(document.id, chapter_index)
        ]

    def reindex_meanings(self, document_id: int, dictionary: Dictionary) -> int:
        """Sets meaning_rank on the book's DocumentWord and ChapterWord rows from their sentences
        (same rule as when a book is processed); returns how many rows changed. Does not commit."""
        senses_of: dict[str, list[Sense]] = {}

        def senses(lemma: str) -> list[Sense]:
            if lemma not in senses_of:
                senses_of[lemma] = dictionary.senses(lemma)
            return senses_of[lemma]

        rows: list[tuple[DocumentWord | ChapterWord, Word]] = [
            *self._words.document_word_rows(document_id),
            *self._words.chapter_word_rows(document_id),
        ]
        changed = 0
        for row, word in rows:
            new = _meaning_rank(word.lemma, row.pos, row.context_sentence, senses(word.lemma))
            if new != row.meaning_rank:
                row.meaning_rank = new
                changed += 1
        return changed


def definitions_in_context(
    word: Word, pos: PartOfSpeech | None, meaning_rank: int | None = None
) -> list[Definition]:
    """The word's definitions: the meaning the sentence uses first (`meaning_rank`, if known),
    then those for the part of speech the book uses."""
    return sorted(
        word.definitions,
        key=lambda d: (d.sense_rank != meaning_rank, d.pos != pos, d.sense_rank),
    )


def _meaning_rank(
    lemma: str, pos: PartOfSpeech | None, sentence: str | None, senses: list[Sense]
) -> int | None:
    """The sense_rank best_sense picks for this sentence, if it isn't the first for `pos`."""
    if pos is None or not sentence:
        return None
    same_pos = [s for s in senses if s.pos == pos.value]
    if not same_pos:
        return None
    chosen = best_sense(sentence, lemma, same_pos)
    return chosen if chosen != same_pos[0].rank else None


def _definitions(senses: list[Sense], source: str) -> list[Definition]:
    return [
        Definition(pos=s.pos, text=s.definition, source=source, sense_rank=s.rank) for s in senses
    ]


def _appearances(item: ExtractedWord) -> tuple[Appearance, ...]:
    """Every chapter a word appears in; just its first appearance if nothing more was recorded."""
    return item.appearances or (
        Appearance(
            item.chapter_index, item.first_position, item.context_sentence, item.context_form
        ),
    )
