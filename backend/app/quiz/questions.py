"""Question generation (docs/PROJECT_PLAN.md §5.3, §5.6).

A `QuestionGenerator` turns a target word and a pool of other words into a question:

- **meaning** (`definition_mcq`): the word; pick its definition from four.
- **reverse**: a definition; pick the word it belongs to.
- **fill in the blank**: the book's own sentence with the word blanked out; pick the word.

Wrong options come from other words of the same part of speech and similar difficulty (supplied by
the caller), never from the target's synonyms, so exactly one option is right; among those, options
close in length to the answer win so the odd one out isn't a giveaway. Phase 5 adds an LLM generator
behind the same protocol.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random
from typing import Protocol

from app.core.enums import QuestionType

BLANK = "_____"


class NotEnoughDistractorsError(Exception):
    """The pool didn't have enough usable wrong options; try a wider pool or another word."""


class QuestionNotPossibleError(Exception):
    """This kind of question can't be made for the word (e.g. no sentence to blank)."""


@dataclass(frozen=True)
class Target:
    lemma: str
    definition: str  # the meaning in the book's sense
    synonyms: frozenset[str]  # words that share a meaning with the target; never used as options
    context_sentence: str | None = None
    context_form: str | None = None  # the word as written in the sentence ("regulating")


@dataclass(frozen=True)
class Candidate:
    """Another word, and its meaning, that could serve as a wrong option."""

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


def _wrong_options(
    target: Target,
    candidates: Sequence[Candidate],
    answer: str,
    option_of: Callable[[Candidate], str],
    count: int,
) -> list[str]:
    """`count` distinct wrong options, closest in length to `answer` (ties keep pool order)."""
    usable: list[str] = []
    seen = {_normalized(answer), _normalized(target.definition), target.lemma}
    for candidate in candidates:
        if candidate.lemma == target.lemma or candidate.lemma in target.synonyms:
            continue
        # The same meaning, or the same word twice, would make two options right.
        keys = {_normalized(candidate.definition), candidate.lemma}
        if keys & seen:
            continue
        seen |= keys
        usable.append(option_of(candidate))
    if len(usable) < count:
        raise NotEnoughDistractorsError(target.lemma)
    return sorted(usable, key=lambda o: abs(len(o) - len(answer)))[:count]


def _draft(
    kind: QuestionType,
    prompt: str,
    answer: str,
    wrong: list[str],
    name: str,
    target: Target,
    rng: Random,
) -> QuestionDraft:
    options = [answer, *wrong]
    rng.shuffle(options)  # a fresh order every time the word is asked
    return QuestionDraft(
        type=kind,
        prompt=prompt,
        options=options,
        correct_index=options.index(answer),
        generator=name,
        source_sentence=target.context_sentence,
    )


class DefinitionQuestionGenerator:
    """Asks what a word means: one correct definition and `options - 1` wrong ones."""

    name = "wordnet-rules"

    def __init__(self, options: int = 4) -> None:
        self._options = options

    def generate(
        self, target: Target, candidates: Sequence[Candidate], rng: Random
    ) -> QuestionDraft:
        wrong = _wrong_options(
            target, candidates, target.definition, lambda c: c.definition, self._options - 1
        )
        kind = QuestionType.DEFINITION_MCQ
        return _draft(kind, target.lemma, target.definition, wrong, self.name, target, rng)


class ReverseQuestionGenerator:
    """Shows a meaning and asks which word it belongs to."""

    name = "wordnet-reverse"

    def __init__(self, options: int = 4) -> None:
        self._options = options

    def generate(
        self, target: Target, candidates: Sequence[Candidate], rng: Random
    ) -> QuestionDraft:
        wrong = _wrong_options(
            target, candidates, target.lemma, lambda c: c.lemma, self._options - 1
        )
        kind = QuestionType.REVERSE
        return _draft(kind, target.definition, target.lemma, wrong, self.name, target, rng)


class FillInBlankQuestionGenerator:
    """The book's sentence with the word blanked out; pick the word that fits."""

    name = "book-sentence"

    def __init__(self, options: int = 4) -> None:
        self._options = options

    def generate(
        self, target: Target, candidates: Sequence[Candidate], rng: Random
    ) -> QuestionDraft:
        prompt = blank_out(target.context_sentence, target.context_form)
        if prompt is None:
            raise QuestionNotPossibleError(target.lemma)
        wrong = _wrong_options(
            target, candidates, target.lemma, lambda c: c.lemma, self._options - 1
        )
        kind = QuestionType.FILL_IN_BLANK
        return _draft(kind, prompt, target.lemma, wrong, self.name, target, rng)


def blank_out(sentence: str | None, form: str | None) -> str | None:
    """The sentence with the first whole-word occurrence of `form` replaced by a blank."""
    if not sentence or not form:
        return None
    pattern = re.compile(rf"(?<![\w-]){re.escape(form)}(?![\w-])", re.IGNORECASE)
    blanked, count = pattern.subn(BLANK, sentence, count=1)
    return blanked if count else None
