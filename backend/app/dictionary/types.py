"""What the app needs from a dictionary, whichever one supplies the definitions."""

from dataclasses import dataclass
from typing import Protocol


class DictionaryUnavailableError(Exception):
    """The dictionary data isn't installed (see `python -m app.dictionary.install`)."""


@dataclass(frozen=True, slots=True)
class Sense:
    pos: str  # noun, verb, adjective or adverb
    definition: str
    rank: int  # 0 = the dictionary's first (usually most common) sense of the lemma


class Dictionary(Protocol):
    source: str  # stored with each definition, e.g. "oewn:2025"

    def senses(self, lemma: str) -> list[Sense]:
        """The lemma's meanings, best first; empty if the dictionary doesn't know it."""
        ...

    def synonyms(self, lemma: str) -> frozenset[str]:
        """Words sharing at least one meaning with the lemma (never wrong options in a quiz)."""
        ...
