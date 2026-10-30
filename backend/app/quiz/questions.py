"""Question generation (docs/PROJECT_PLAN.md §5.3, §5.6).

A `QuestionGenerator` turns a target word and a pool of other words into a question. The MVP has
one generator: "pick the meaning" with four definitions. Wrong options come from other words of the
same part of speech and similar difficulty (supplied by the caller), never from the target's
synonyms, so exactly one option is right; among those, options close in length to the answer win.
Phase 5 adds an LLM generator behind the same protocol.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from random import Random
from typing import Protocol

from app.core.enums import QuestionType


class NotEnoughDistractorsError(Exception):
    """The pool didn't have enough usable wrong options; try a wider pool or another word."""


@dataclass(frozen=True)
class Target:
    lemma: str
    definition: str  # the correct option
    synonyms: frozenset[str]  # words that share a meaning with the target; never used as options
    context_sentence: str | None = None


@dataclass(frozen=True)
class Candidate:
    """Another word's meaning that could serve as a wrong option."""

    lemma: str
    definition: str


@dataclass(frozen=True)
class QuestionDraft:
    type: QuestionType
    prompt: str
    options: list[str]
    correct_index: int
    generator: str
    source_sentence: str | None


class QuestionGenerator(Protocol):
    name: str

    def generate(
        self, target: Target, candidates: Sequence[Candidate], rng: Random
    ) -> QuestionDraft: ...


def _normalized(text: str) -> str:
    return " ".join(text.lower().split())


class DefinitionQuestionGenerator:
    """Asks what a word means: one correct definition and `options - 1` wrong ones."""

    name = "wordnet-rules"

    def __init__(self, options: int = 4) -> None:
        self._options = options

    def generate(
        self, target: Target, candidates: Sequence[Candidate], rng: Random
    ) -> QuestionDraft:
        usable: list[str] = []
        seen = {_normalized(target.definition)}
        for candidate in candidates:
            if candidate.lemma == target.lemma or candidate.lemma in target.synonyms:
                continue
            if _normalized(candidate.definition) in seen:  # identical meaning: both would be right
                continue
            seen.add(_normalized(candidate.definition))
            usable.append(candidate.definition)
        if len(usable) < self._options - 1:
            raise NotEnoughDistractorsError(target.lemma)
        # Options of similar length, so the longest one isn't a giveaway (ties keep pool order).
        wrong = sorted(usable, key=lambda d: abs(len(d) - len(target.definition)))
        wrong = wrong[: self._options - 1]

        options = [target.definition, *wrong]
        rng.shuffle(options)  # a fresh order every time the word is asked
        return QuestionDraft(
            type=QuestionType.DEFINITION_MCQ,
            prompt=target.lemma,
            options=options,
            correct_index=options.index(target.definition),
            generator=self.name,
            source_sentence=target.context_sentence,
        )
