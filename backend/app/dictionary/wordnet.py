"""Definitions from Open English WordNet (CC BY 4.0), read through the `wn` library.

`wn` keeps its data in a SQLite file under `data_dir`; install a lexicon once with
`python -m app.dictionary.install`. Lookups don't lemmatise: callers pass lemmas (spaCy made them).
"""

from pathlib import Path
from threading import Lock

import wn

from app.dictionary.types import DictionaryUnavailableError, Sense

_POS_NAMES = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective", "r": "adverb"}

# `wn.config` is process-wide, so every WordNetDictionary must agree on the data directory.
_config_lock = Lock()


def use_data_dir(data_dir: Path) -> None:
    with _config_lock:
        data_dir.mkdir(parents=True, exist_ok=True)
        wn.config.data_directory = data_dir


def install(data_dir: Path, lexicon: str) -> None:
    """Downloads `lexicon` (e.g. "oewn:2025") into `data_dir` unless it's already there."""
    use_data_dir(data_dir)
    if not any(lex.specifier() == lexicon for lex in wn.lexicons()):
        wn.download(lexicon)


class WordNetDictionary:
    def __init__(self, data_dir: Path, lexicon: str, senses_per_pos: int = 3) -> None:
        use_data_dir(data_dir)
        try:
            self._wordnet = wn.Wordnet(lexicon)
        except wn.Error:
            raise DictionaryUnavailableError(
                f"WordNet lexicon {lexicon!r} isn't installed;"
                " run `python -m app.dictionary.install`"
            ) from None
        self.source = lexicon
        self._senses_per_pos = senses_per_pos

    def senses(self, lemma: str) -> list[Sense]:
        found: list[Sense] = []
        per_pos: dict[str, int] = {}
        seen: set[str] = set()
        for word in self._wordnet.words(lemma):  # also matches variant spellings ("colour")
            pos = _POS_NAMES.get(word.pos)
            if pos is None:
                continue
            for sense in word.senses():
                definition = sense.synset().definition()
                if (
                    not definition
                    or definition in seen
                    or per_pos.get(pos, 0) >= self._senses_per_pos
                ):
                    continue
                seen.add(definition)
                per_pos[pos] = per_pos.get(pos, 0) + 1
                found.append(Sense(pos=pos, definition=definition, rank=len(found)))
        return found
