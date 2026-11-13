"""The data part of migration eb1e43496bdc: learned and once-learned words get first_learned_at."""

import importlib
import sqlite3

migration = importlib.import_module(
    "app.db.migrations.versions.eb1e43496bdc_words_remember_when_they_were_first_"
)


def test_learned_and_once_learned_words_get_a_first_learned_time() -> None:
    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE user_words (id INTEGER, status TEXT, was_learned BOOLEAN, "
        "learned_at TEXT, last_reviewed_at TEXT, first_learned_at TEXT)"
    )
    db.executemany(
        "INSERT INTO user_words VALUES (?, ?, ?, ?, ?, NULL)",
        [
            (1, "learned", 1, "2026-10-01", "2026-10-20"),  # learned: its learned time
            (2, "learning", 1, None, "2026-10-15"),  # fell back below 100: last review
            (3, "learning", 0, None, "2026-10-16"),  # never learned
            (4, "new", 0, None, None),
        ],
    )

    db.execute(migration.FIRST_LEARNED, {"yes": 1})

    found = db.execute("SELECT id, first_learned_at FROM user_words ORDER BY id").fetchall()
    assert found == [(1, "2026-10-01"), (2, "2026-10-15"), (3, None), (4, None)]
