"""The data part of migration b003d670f797 (Gutenberg numbers and slugs for the classics)."""

import importlib

migration = importlib.import_module(
    "app.db.migrations.versions.b003d670f797_gutenberg_books_and_shelves"
)


def test_classics_get_their_gutenberg_number_and_a_slug() -> None:
    rows = [
        (1, "Alice's Adventures in Wonderland", "gutenberg-11.epub"),
        (2, "Dracula", "gutenberg-345.epub"),
        (3, "My own notes", "notes.pdf"),  # not a Gutenberg file: left alone
    ]

    assert migration.classic_ids_and_slugs(rows) == [
        {"id": 1, "gutenberg_id": 11, "slug": "alices-adventures-in-wonderland"},
        {"id": 2, "gutenberg_id": 345, "slug": "dracula"},
    ]


def test_slugs_stay_unique() -> None:
    rows = [(1, "Emma", "gutenberg-158.epub"), (2, "Emma", "gutenberg-19839.epub")]

    slugs = [u["slug"] for u in migration.classic_ids_and_slugs(rows)]

    assert slugs == ["emma", "emma-2"]
