"""The placement check and each reader's word level (see app.quiz.placement for the rules)."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random

from sqlalchemy.orm import Session
from wordfreq import top_n_list, zipf_frequency

from app.db.models import User
from app.dictionary.types import Dictionary
from app.quiz.placement import (
    BAND_WIDTH,
    BANDS,
    FAKES,
    PSEUDOWORDS,
    SET_ASIDE_BELOW,
    Answer,
    easy_above,
    estimate_level,
    level_from_quiz,
    pick_items,
)
from app.repositories.placement import PlacementRepository

_CANDIDATES_PER_BAND = 200  # plenty, so every check differs
# The check is the first thing a new reader sees: keep it free of unpleasant words.
_AVOID = frozenset(
    {
        "abortion",
        "bastard",
        "cocaine",
        "erotic",
        "fetish",
        "genocide",
        "heroin",
        "masturbation",
        "nazi",
        "nude",
        "orgasm",
        "orgy",
        "penis",
        "porn",
        "pornography",
        "rape",
        "sex",
        "sexual",
        "slut",
        "suicide",
        "terrorist",
        "torture",
        "vagina",
        "whore",
    }
)
_MIN_HISTORY = 40  # answers needed before past answers say anything about a level
_EASY_LIMIT = 300


class PlacementError(Exception):
    """A request the API rejects with the message as the reason."""


@dataclass(frozen=True)
class SavedLevel:
    level: float
    set_aside: int  # easy words in learning that went back to probably known


@dataclass(frozen=True)
class EasyWord:
    lemma: str
    meaning: str | None
    book: str


def zipf(word: str) -> float | None:
    """The word's Zipf value, or None for the check's made-up words."""
    return None if word in PSEUDOWORDS else zipf_frequency(word, "en")


_found: dict[float, tuple[str, ...]] = {}  # worked out once per process


def _candidates(dictionary: Dictionary) -> dict[float, tuple[str, ...]]:
    """Plain dictionary words for each band (no names or slang: WordNet must know them)."""
    if _found:
        return _found
    found: dict[float, list[str]] = {band: [] for band in BANDS}
    for word in top_n_list("en", 200_000):
        if not (word.isalpha() and word.islower() and len(word) >= 4) or word in _AVOID:
            continue
        value = zipf_frequency(word, "en")
        band = next((b for b in BANDS if abs(value - b) < BAND_WIDTH), None)
        if band is None or len(found[band]) >= _CANDIDATES_PER_BAND:
            continue
        if dictionary.senses(word):
            found[band].append(word)
        if all(len(words) >= _CANDIDATES_PER_BAND for words in found.values()):
            break
    _found.update({band: tuple(words) for band, words in found.items()})
    return _found


class PlacementService:
    def __init__(
        self, session: Session, dictionary: Callable[[], Dictionary], rng: Random | None = None
    ) -> None:
        self._session = session
        self._repo = PlacementRepository(session)
        self._dictionary = dictionary
        self._rng = rng or Random()

    def items(self) -> list[str]:
        """A fresh check: 20 words in random order."""
        dictionary = self._dictionary()
        fakes = [w for w in PSEUDOWORDS if not dictionary.senses(w)]  # truly made up
        if len(fakes) < FAKES:  # the dictionary grew to know some: better any than none
            fakes = list(PSEUDOWORDS)
        return pick_items(_candidates(dictionary), fakes, self._rng)

    def save(self, user_id: int, answers: Sequence[tuple[str, bool]]) -> SavedLevel:
        """Works out and keeps the user's level from their answers to the check."""
        if len(answers) < len(BANDS):
            raise PlacementError("Answer all the words first")
        level = estimate_level(
            [Answer(zipf(word.strip().lower()), known) for word, known in answers]
        )
        return self.set_level(user_id, level)

    def set_level(self, user_id: int, level: float) -> SavedLevel:
        """Keeps the level, and takes easy words with little progress out of the quiz."""
        self._user(user_id).vocab_level = level
        moved = self._repo.set_aside_easy(user_id, easy_above(level), SET_ASIDE_BELOW)
        self._session.commit()
        return SavedLevel(level, moved)

    def level(self, user_id: int) -> float | None:
        return self._user(user_id).vocab_level

    def estimate_from_history(self, user_id: int) -> float | None:
        """A level from past answers (first answer to each word right or wrong) and words marked
        known, for readers who never took the check. None while there are too few."""
        answers = [Answer(z, right) for z, right in self._repo.first_answers(user_id)]
        answers += [Answer(z, True) for z in self._repo.known_zipfs(user_id)]
        if len(answers) < _MIN_HISTORY:
            return None
        return level_from_quiz(answers)

    def probably_known(self, user_id: int) -> list[EasyWord]:
        """Words from the user's current reads that are probably known to them (by their level,
        or the default cutoff without one): the quiz skips these."""
        above = easy_above(self._user(user_id).vocab_level)
        rows = self._repo.probably_known(user_id, above, _EASY_LIMIT)
        return [
            EasyWord(word.lemma, word.definitions[0].text if word.definitions else None, title)
            for word, title in rows
        ]

    def _user(self, user_id: int) -> User:
        user = self._session.get(User, user_id)
        if user is None:
            raise LookupError(f"no user {user_id}")
        return user
