"""Pick which of a word's dictionary meanings a book sentence uses (pure: standard library only)."""

import re
from collections.abc import Sequence

from app.dictionary.types import Sense

_STOPWORDS = frozenset(
    """the and for are but not you all any can had her was one our out has his how its may who
    did get him she too use via with that which from have been this they them then than there
    these those their what when where while whom whose will would could should shall about above
    after again against because before being below between both does doing down during each
    few further here into more most other over same some such only own very just once under
    until upon your yours ours theirs himself herself itself myself yourself themselves were
    also onto off nor yet per etc often usually especially something someone anything anyone
    many much every either neither whether however although though through within without
    among across along around toward towards""".split()  # noqa: SIM905
)

_WORD = re.compile(r"[a-z]+")
# Tried in order; the first that matches (and leaves 3+ letters) is stripped.
_SUFFIXES = (
    ("ingly", ""),
    ("edly", ""),
    ("ness", ""),
    ("ment", ""),
    ("ing", ""),
    ("ies", "y"),
    ("ied", "y"),
    ("ed", ""),
    ("es", ""),
    ("ly", ""),
    ("s", ""),
)


def _stem(word: str) -> str:
    for suffix, replacement in _SUFFIXES:
        if word.endswith(suffix):
            stem = word[: -len(suffix)] + replacement
            if len(stem) >= 3:
                return stem
    return word


def content_stems(text: str) -> frozenset[str]:
    """Stems of the text's meaningful words (3+ letters, no stopwords), crudely suffix-stripped."""
    return frozenset(
        _stem(word)
        for word in _WORD.findall(text.lower())
        if len(word) >= 3 and word not in _STOPWORDS
    )


def _scores(sentence: str, lemma: str, senses: Sequence[Sense]) -> list[int]:
    context = content_stems(sentence) - content_stems(lemma)
    return [
        len(context & content_stems(f"{sense.definition} {' '.join(sense.examples)}"))
        for sense in senses
    ]


def rank_senses(sentence: str, lemma: str, senses: Sequence[Sense]) -> list[int]:
    """Indexes into `senses`, best fit to the sentence first; ties keep the input order."""
    scores = _scores(sentence, lemma, senses)
    return sorted(range(len(senses)), key=lambda i: -scores[i])


def best_sense(sentence: str, lemma: str, senses: Sequence[Sense]) -> int | None:
    """The `rank` of the sense the sentence most likely uses.

    The top-ranked sense wins only if it beats the dictionary's first sense; otherwise the
    first sense stays. None when there are no senses.
    """
    if not senses:
        return None
    scores = _scores(sentence, lemma, senses)
    top = sorted(range(len(senses)), key=lambda i: -scores[i])[0]
    return senses[top].rank if scores[top] > scores[0] else senses[0].rank
