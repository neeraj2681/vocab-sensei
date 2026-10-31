import pytest

from app.extraction.chapters import is_heading, split_at_headings

BODY = "It was a damp, drizzly November in my soul, and I thought I would sail about a little. " * 2


@pytest.mark.parametrize(
    "line",
    ["CHAPTER 1. Loomings.", "Chapter XII", "BOOK TWO", "Part III: The Return", "LETTER 4"],
)
def test_recognises_chapter_headings(line: str) -> None:
    assert is_heading(line)


@pytest.mark.parametrize(
    "line",
    [
        "chapter 5 was where it all began",  # prose, lower case
        "Chapters of my life",
        "CHAPTER 1. " + "very long " * 15,  # longer than a heading
        "Call me Ishmael.",
    ],
)
def test_ignores_ordinary_lines(line: str) -> None:
    assert not is_heading(line)


def test_splits_at_headings_and_keeps_the_preamble() -> None:
    chapters = split_at_headings(
        ["Moby Dick; or, The Whale. " + BODY, "CHAPTER 1. Loomings.", BODY, "CHAPTER 2.", BODY]
    )

    assert [c.title for c in chapters] == [None, "CHAPTER 1. Loomings.", "CHAPTER 2."]
    assert chapters[1].text == BODY


def test_a_table_of_contents_does_not_start_chapters() -> None:
    contents = ["CONTENTS", "CHAPTER 1. Loomings.", "CHAPTER 2. The Carpet-Bag.", "Epilogue"]
    front_matter = "ETYMOLOGY. While you take in hand to school others... " + BODY

    chapters = split_at_headings(
        [*contents, front_matter, "CHAPTER 1. Loomings.", BODY, "CHAPTER 2. The Carpet-Bag.", BODY]
    )

    assert [c.title for c in chapters] == [
        None,
        "CHAPTER 1. Loomings.",
        "CHAPTER 2. The Carpet-Bag.",
    ]
    assert chapters[0].text.endswith(front_matter)  # the contents and front matter stay together


def test_chapter_numbers_may_repeat_across_books() -> None:
    chapters = split_at_headings(
        ["BOOK ONE", "CHAPTER 1.", BODY, "CHAPTER 2.", BODY, "BOOK TWO", "CHAPTER 1.", BODY]
    )

    assert [c.title for c in chapters] == ["CHAPTER 1.", "CHAPTER 2.", "CHAPTER 1."]


def test_headings_without_text_are_dropped() -> None:
    chapters = split_at_headings(["BOOK ONE", "CHAPTER 1.", BODY, "CHAPTER 2.", BODY])

    assert [c.title for c in chapters] == ["CHAPTER 1.", "CHAPTER 2."]


def test_text_without_headings_is_one_chapter() -> None:
    chapters = split_at_headings([BODY, BODY])

    assert len(chapters) == 1
    assert chapters[0].title is None
    assert chapters[0].text == f"{BODY}\n{BODY}"


def test_short_sections_merge_into_the_next() -> None:
    chapters = split_at_headings(["PART ONE", "A short note.", "CHAPTER 1.", BODY])

    assert [c.title for c in chapters] == ["PART ONE"]
    assert chapters[0].text == f"A short note.\n{BODY}"


def test_a_contents_entry_before_front_matter_is_not_a_chapter() -> None:
    contents = ["CHAPTER 1. Loomings.", "CHAPTER 2. The Carpet-Bag.", "CHAPTER 3. The Spouter-Inn."]
    front_matter = "ETYMOLOGY. While you take in hand to school others... " + BODY

    chapters = split_at_headings(
        [*contents, front_matter, *[p for h in contents for p in (h, BODY)]]
    )

    assert [c.title for c in chapters] == [None, *contents]
    assert front_matter in chapters[0].text
