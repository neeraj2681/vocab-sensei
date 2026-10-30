"""Which new words to learn next when several books are read at once (docs/PROJECT_PLAN.md §5.2).

Each current read supplies its own queue of new words in reading order. The queues share the slots
by priority: with n books the weights are n, n-1, ..., 1 (three books → 3:2:1), so the main book
moves fastest while the others keep progressing. A word that appears in several books is taken once.
"""

from collections.abc import Callable, Hashable, Sequence


def mix_by_priority[T](
    queues: Sequence[Sequence[T]], count: int, key: Callable[[T], Hashable]
) -> list[T]:
    """Up to `count` items from `queues` (highest priority first), interleaved by weight.

    Uses smooth weighted round-robin, so picks are spread out (A B A C B A) rather than
    bunched (A A A B B C). An empty queue drops out and its share goes to the others.
    """
    weights = [len(queues) - i for i in range(len(queues))]
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
