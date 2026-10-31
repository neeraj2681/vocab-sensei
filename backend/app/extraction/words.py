"""Finds the words worth learning in a book, in reading order.

spaCy splits the text into sentences and tokens, tags parts of speech and reduces each word to
its lemma ("perambulating" -> "perambulate"). We keep content words (nouns, verbs, adjectives,
adverbs) whose lemma is rare enough by wordfreq's Zipf score, skipping names and stopwords.
"""

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from functools import cache

import spacy
from spacy.language import Language
from spacy.tokens import Token
from wordfreq import zipf_frequency

from app.core.config import ExtractionSettings
from app.core.enums import PartOfSpeech
from app.extraction.types import ParsedChapter

SPACY_MODEL = "en_core_web_sm"
# spaCy's tags for content words; PROPN (names) is deliberately absent.
_CONTENT_POS = {
    "NOUN": PartOfSpeech.NOUN,
    "VERB": PartOfSpeech.VERB,
    "ADJ": PartOfSpeech.ADJECTIVE,
    "ADV": PartOfSpeech.ADVERB,
}


@dataclass(frozen=True)
class ExtractedWord:
    lemma: str
    zipf: float
    chapter_index: int  # chapter where the word first appears
    first_position: int  # token offset inside that chapter
    occurrences: int  # across the whole book
    context_sentence: str  # the sentence of the first appearance
    context_form: str  # the word as written in that sentence ("regulating" for "regulate")
    pos: PartOfSpeech  # how the book uses the word most often ("damp": adjective, not noun)


@cache
def load_nlp() -> Language:
    """Loaded once per process (~1 s). Parser and NER are skipped; `senter` finds sentences."""
    nlp = spacy.load(SPACY_MODEL, exclude=["parser", "ner"])
    nlp.enable_pipe("senter")
    return nlp


@cache
def _zipf(lemma: str) -> float:
    return zipf_frequency(lemma, "en")


class WordExtractor:
    def __init__(self, settings: ExtractionSettings, nlp: Language | None = None) -> None:
        self._settings = settings
        self._nlp = nlp or load_nlp()

    def extract(self, chapters: Sequence[ParsedChapter]) -> list[ExtractedWord]:
        first_seen: dict[str, ExtractedWord] = {}
        uses: dict[str, Counter[PartOfSpeech]] = {}

        for chapter_index, chapter in enumerate(chapters):
            for position, token in self._tokens(chapter.text):
                lemma = self._learnable_lemma(token)
                if lemma is None:
                    continue
                pos = _CONTENT_POS[token.pos_]
                uses.setdefault(lemma, Counter())[pos] += 1
                if lemma not in first_seen:
                    first_seen[lemma] = ExtractedWord(
                        lemma=lemma,
                        zipf=_zipf(lemma),
                        chapter_index=chapter_index,
                        first_position=position,
                        occurrences=0,
                        context_sentence=self._context(token),
                        context_form=token.text,
                        pos=pos,
                    )

        words = [
            # most_common keeps first-seen order on ties, so a tie goes to the first use
            replace(w, occurrences=uses[w.lemma].total(), pos=uses[w.lemma].most_common(1)[0][0])
            for w in first_seen.values()
        ]
        return sorted(words, key=lambda w: (w.chapter_index, w.first_position))

    def _tokens(self, text: str) -> Iterable[tuple[int, Token]]:
        """(position in chapter, token). Paragraphs are processed one by one to bound memory."""
        offset = 0
        for doc in self._nlp.pipe(line for line in text.splitlines() if line.strip()):
            for token in doc:
                yield offset + token.i, token
            offset += len(doc)

    def _learnable_lemma(self, token: Token) -> str | None:
        if token.pos_ not in _CONTENT_POS or token.is_stop or not token.is_alpha:
            return None
        lemma = token.lemma_.lower()
        if len(lemma) < self._settings.min_length or not lemma.isalpha():
            return None
        if not self._settings.min_zipf <= _zipf(lemma) < self._settings.max_zipf:
            return None
        return lemma

    def _context(self, token: Token) -> str:
        sentence = " ".join(token.sent.text.split())
        limit = self._settings.context_chars
        if len(sentence) <= limit:
            return sentence
        # Keep a window around the word so it is always visible in the snippet.
        center = sentence.find(token.text)
        start = max(0, min(center - limit // 2, len(sentence) - limit))
        snippet = sentence[start : start + limit].strip()
        return f"{'…' if start > 0 else ''}{snippet}{'…' if start + limit < len(sentence) else ''}"
