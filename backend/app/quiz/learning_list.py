"""Which new words to learn next when several books are read at once (docs/PROJECT_PLAN.md §5.2).

Each current read (at most `MAX_READING`) supplies its own queue of new words in reading order. The
queues take turns, so every book moves at the same pace. A word that appears in several books is
taken once. The words in progress are shared the same way (`share_places`): equal halves of the
places being practised, with a book that has too few words leaving its spare places to the other.

Within a book, words from chapters before the current one (skipped by starting later) are mixed in
the same way at a lower weight: 1 in `EARLIER_CHAPTERS_EVERY` new words.
"""

from collections.abc import Callable, Hashable, Sequence

EARLIER_CHAPTERS_EVERY = 4  # 3 words from the current chapter on, then 1 from before it
SUGGESTED_CHAPTERS = 3  # starting a book, or picking "I'm here": that chapter and the next two
MAX_READING = 2  # books read at once


def share_places[T](queues: Sequence[Sequence[T]], key: Callable[[T], Hashable]) -> list[T]:
    """Every item, one from each queue in turn (each queue best first), duplicates once.

    The first `cap` are the ones being practised: an equal share per queue, and a queue too short
    for its share leaves the rest to the others.
    """
    return mix_by_priority(queues, sum(len(q) for q in queues), key, [1] * len(queues))


def ahead_then_earlier[T](
    ahead: Sequence[T], earlier: Sequence[T], count: int, key: Callable[[T], Hashable]
) -> list[T]:
    """One book's queue: mostly words still ahead of the reader, some from skipped chapters."""
    return mix_by_priority([ahead, earlier], count, key, [EARLIER_CHAPTERS_EVERY - 1, 1])


def mix_by_priority[T](
    queues: Sequence[Sequence[T]],
    count: int,
    key: Callable[[T], Hashable],
    weights: Sequence[int] | None = None,
) -> list[T]:
    """Up to `count` items from `queues` (highest priority first), interleaved by weight.

    Weights default to equal. Uses smooth weighted round-robin, so picks are spread out
    (A B A C B A) rather than bunched (A A A B B C). An empty queue drops out and its share goes
    to the others.
    """
    if weights is None:
        weights = [1] * len(queues)
    credit = [0] * len(queues)
    positions = [0] * len(queues)
    taken: set[Hashable] = set()
    picked: list[T] = []

    while len(picked) < count:
        active = [i for i in range(len(queues)) if positions[i] < len(queues[i])]
        if not active:
            break
        for i in active:
            credit[i] += weights[i]
        best = max(active, key=lambda i: credit[i])  # ties go to the higher priority
        credit[best] -= sum(weights[i] for i in active)

        item = queues[best][positions[best]]
        positions[best] += 1
        if key(item) not in taken:
            taken.add(key(item))
            picked.append(item)
    return picked


def suggested_chapters(index: int, total: int) -> list[int]:
    """The chapters marked as being read when the reader is at `index`: it and the next two."""
    return list(range(index, min(index + SUGGESTED_CHAPTERS, total))) or [0]


def reading_chapters(saved: Sequence[int], current: int, total: int) -> list[int]:
    """The chapters being read, in order: those the reader chose (that still exist), or the
    suggested ones around `current` for reads that never chose."""
    chosen = sorted({index for index in saved if 0 <= index < total})
    return chosen or suggested_chapters(current, total)
