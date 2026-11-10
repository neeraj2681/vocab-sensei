"""The placement check: how hard a word has to be before someone doesn't know it.

Words carry a difficulty on the Zipf scale (how common they are: 7 = "the", 1 = very rare).
The check shows `PER_BAND` real words from each band in `BANDS`, mixed with `FAKES` made-up
words, and the reader answers "I know it" or "Not sure". Their level is the Zipf value where
"I know it" turns into "Not sure": words clearly more common than that are probably known and
kept out of the quiz.

Claiming to know made-up words means the other answers are optimistic too, so each one moves
the level towards rarer-is-unknown (a standard correction in yes/no vocabulary tests, e.g.
LexTALE).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random

BANDS = (5.0, 4.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.5)  # Zipf, common to rare
PER_BAND = 2
FAKES = 4  # 8 bands x 2 + 4 = 20 questions
BAND_WIDTH = 0.25  # a word belongs to a band within this distance of it
FAKE_PENALTY = 0.35  # Zipf added to the level for each made-up word "known"
MARGIN = 0.5  # words more common than level + MARGIN count as probably known
# Without a level, words more common than this count as probably known ("accomplish" is 3.7,
# "lugubrious" 1.9); books keep words up to Zipf 4.0, which let in too many easy ones.
DEFAULT_EASY_ABOVE = 3.5
# When a level is set, easy words already being learned with less than this score leave the quiz
# (as probably known); words with more progress stay.
SET_ASIDE_BELOW = 30
LOWEST, HIGHEST = 1.0, 6.0  # the level always stays within these
QUIZ_KNOWN = 0.9  # from quiz history, a band counts as known at this share answered right

# Pronounceable but not English (checked against the word list and the dictionary in the tests).
PSEUDOWORDS = (
    "plontish",
    "vurmicate",
    "glorbent",
    "snerkle",
    "branticle",
    "fendolate",
    "crombish",
    "stelvorous",
    "quindrel",
    "morbisant",
    "pleskin",
    "tarvulent",
    "drimmock",
    "obsulate",
    "framblous",
    "wendicate",
    "clopherous",
    "spindlewort",
)


@dataclass(frozen=True)
class Answer:
    zipf: float | None  # None: a made-up word
    known: bool


def pick_items(
    candidates: Mapping[float, Sequence[str]], fakes: Sequence[str], rng: Random
) -> list[str]:
    """The check's words: `PER_BAND` real ones per band plus `FAKES` made-up ones, shuffled."""
    words = [w for band in BANDS for w in rng.sample(list(candidates[band]), PER_BAND)]
    words += rng.sample(list(fakes), FAKES)
    rng.shuffle(words)
    return words


def estimate_level(answers: Sequence[Answer]) -> float:
    """The Zipf value where "I know it" turns into "Not sure".

    Tries every boundary between bands and keeps the one that agrees with the most answers (known
    above it, not known below); a tie goes to the middle of the tied ones. Each made-up word "known"
    then raises it by `FAKE_PENALTY`.
    """
    real = [(a.zipf, a.known) for a in answers if a.zipf is not None]
    claimed_fakes = sum(1 for a in answers if a.zipf is None and a.known)
    steps = int((HIGHEST - LOWEST) / BAND_WIDTH)
    candidates = [LOWEST + i * BAND_WIDTH for i in range(steps + 1)]

    def agreement(level: float) -> int:
        return sum(1 for zipf, known in real if (zipf >= level) == known)

    best = max((agreement(c) for c in candidates), default=0)
    tied = [c for c in candidates if agreement(c) == best]
    level = tied[len(tied) // 2] if tied else 4.0
    return round(min(HIGHEST, max(LOWEST, level + FAKE_PENALTY * claimed_fakes)), 2)


def level_from_quiz(answers: Sequence[Answer], min_per_band: int = 10) -> float | None:
    """A level from quiz history: first answers right or wrong, and words marked known.

    Multiple choice overstates knowledge (a guess is right 1 time in 4 and wrong options can be
    easy to rule out), so a band only counts as known at `QUIZ_KNOWN` (90%) right. Going from the
    most common band down, the level is set so that words from the last such band on are
    "probably known". None when no band qualifies or there's too little to go on.
    """
    counts: dict[float, list[int]] = {}
    for a in answers:
        if a.zipf is None:
            continue
        band = round(a.zipf / BAND_WIDTH / 2) * BAND_WIDTH * 2  # nearest half point
        known, total = counts.setdefault(band, [0, 0])
        counts[band] = [known + a.known, total + 1]
    lowest_known: float | None = None
    for band in sorted(counts, reverse=True):
        known, total = counts[band]
        if total < min_per_band:
            continue
        if known / total < QUIZ_KNOWN:
            break
        lowest_known = band
    if lowest_known is None:
        return None
    return round(lowest_known - BAND_WIDTH - MARGIN, 2)  # probably known from its lower edge


def probably_known_above(level: float) -> float:
    """Words more common than this (higher Zipf) are probably known at `level`."""
    return level + MARGIN


def easy_above(level: float | None) -> float:
    """Words more common than this are probably known: from the reader's level, or by default."""
    return probably_known_above(level) if level is not None else DEFAULT_EASY_ABOVE


def level_name(level: float) -> str:
    """A friendly name for a level."""
    if level <= 2.25:
        return "Expert"
    if level <= 3.0:
        return "Advanced"
    if level <= 3.75:
        return "Confident"
    if level <= 4.5:
        return "Growing"
    return "Getting started"
