from random import Random

from wordfreq import zipf_frequency

from app.quiz.placement import (
    BANDS,
    FAKES,
    PER_BAND,
    PSEUDOWORDS,
    Answer,
    easy_above,
    estimate_level,
    level_name,
    pick_items,
    probably_known_above,
)


def reader_who_knows_down_to(level: float, fakes_claimed: int = 0) -> list[Answer]:
    """Knows every check word at least as common as `level`, none rarer."""
    real = [Answer(band, band >= level) for band in BANDS for _ in range(PER_BAND)]
    fake = [Answer(None, i < fakes_claimed) for i in range(FAKES)]
    return real + fake


def test_a_check_is_twenty_words_with_four_made_up() -> None:
    candidates = {band: [f"w{band}-{i}" for i in range(5)] for band in BANDS}

    words = pick_items(candidates, PSEUDOWORDS, Random(1))

    assert len(words) == len(BANDS) * PER_BAND + FAKES == 20
    assert len(set(words)) == 20
    assert sum(w in PSEUDOWORDS for w in words) == FAKES
    for band in BANDS:
        assert sum(w.startswith(f"w{band}-") for w in words) == PER_BAND


def test_the_level_is_where_knowing_stops() -> None:
    assert 2.5 < estimate_level(reader_who_knows_down_to(3.0)) <= 3.0
    assert 1.0 <= estimate_level(reader_who_knows_down_to(1.0)) <= 1.5  # knows them all
    assert estimate_level(reader_who_knows_down_to(9)) > 5.0  # knows none


def test_claiming_made_up_words_makes_the_level_more_cautious() -> None:
    honest = estimate_level(reader_who_knows_down_to(3.0))

    assert estimate_level(reader_who_knows_down_to(3.0, fakes_claimed=2)) == honest + 0.7


def test_the_made_up_words_are_not_english() -> None:
    assert all(zipf_frequency(word, "en") == 0 for word in PSEUDOWORDS)
    assert len(PSEUDOWORDS) >= 2 * FAKES  # enough for a varied check


def test_words_well_above_the_level_are_probably_known() -> None:
    assert probably_known_above(3.0) == 3.5


def test_levels_have_friendly_names() -> None:
    assert [level_name(x) for x in (2.0, 2.75, 3.5, 4.25, 5.0)] == [
        "Expert",
        "Advanced",
        "Confident",
        "Growing",
        "Getting started",
    ]


def test_quiz_history_needs_ninety_percent_right_to_count_as_known() -> None:
    from app.quiz.placement import level_from_quiz

    def band(zipf: float, right: int, total: int) -> list[Answer]:
        return [Answer(zipf, i < right) for i in range(total)]

    # Like a real reader: 96% and 94% on common words, about 80% on rarer ones.
    history = band(4.0, 24, 25) + band(3.5, 47, 50) + band(3.0, 41, 50) + band(2.5, 25, 30)

    level = level_from_quiz(history)

    assert level == 2.75  # probably known from 3.25 up: the 94% band and above
    assert probably_known_above(level) == 3.25
    assert level_from_quiz(band(4.0, 20, 25)) is None  # 80% isn't enough to skip anything
    assert level_from_quiz(band(4.0, 5, 5)) is None  # too few to tell


def test_easy_comes_from_the_level_or_a_default() -> None:
    assert easy_above(2.5) == 3.0
    assert easy_above(None) == 3.5  # no level yet: "accomplish" (3.7) is easy, "lugubrious" not
