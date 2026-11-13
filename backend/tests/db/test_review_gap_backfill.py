"""The data part of migration d9cc76e26117: scores above 100 become a review gap."""

import importlib
import sqlite3

migration = importlib.import_module(
    "app.db.migrations.versions.d9cc76e26117_learned_words_have_a_review_gap"
)


def test_points_over_100_become_weeks_between_reviews() -> None:
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE user_words (id INTEGER, score INTEGER, interval_weeks INTEGER)")
    rows = [(1, 40), (2, 100), (3, 105), (4, 115), (5, 300)]
    db.executemany("INSERT INTO user_words VALUES (?, ?, 1)", rows)

    db.execute(migration.SCORES_TO_GAPS)

    found = db.execute("SELECT id, score, interval_weeks FROM user_words ORDER BY id").fetchall()
    assert found == [(1, 40, 1), (2, 100, 1), (3, 100, 2), (4, 100, 4), (5, 100, 16)]
