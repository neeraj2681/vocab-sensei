"""The data migration that marks words learned before (5d5e67a0b59b)."""

import importlib

backfill = importlib.import_module(
    "app.db.migrations.versions.5d5e67a0b59b_words_remember_being_learned"
)


def test_words_learned_before_are_found_from_their_answers() -> None:
    up_to = [(1, w, 10) for w in (1, 2, 3) for _ in range(10)]  # words 1-3 reach 100
    answers = [
        *up_to,
        (1, 2, -10),  # word 2 slips to 90: still learned before
        *[(1, 3, -10)] * 6,  # word 3 falls to 40: no longer
        *[(1, 4, 10)] * 7,  # word 4 never reached 100
    ]
    words = [
        (1, 1, "learned", 100),
        (1, 2, "learning", 90),
        (1, 3, "learning", 40),
        (1, 4, "learning", 70),
        (1, 5, "learned", 100),  # learned with no answers on record (e.g. before logging)
    ]

    found = backfill.learned_before(answers, words)

    assert found == [
        {"user_id": 1, "word_id": 1},
        {"user_id": 1, "word_id": 2},
        {"user_id": 1, "word_id": 5},
    ]


def test_the_current_score_wins_over_an_old_history() -> None:
    answers = [(1, 1, 10)] * 10  # reached 100 once...
    words = [(1, 1, "learning", 0)]  # ...but was reset with "Learn it again"

    assert backfill.learned_before(answers, words) == []
