from app.quiz.learning_list import (
    mix_by_priority,
    reading_chapters,
    share_places,
    suggested_chapters,
)


def mix(queues: list[list[str]], count: int) -> list[str]:
    return mix_by_priority(queues, count, key=lambda word: word)


def test_books_take_turns() -> None:
    picked = mix([["a1", "a2", "a3", "a4"], ["b1", "b2", "b3"]], 6)

    books = [word[0] for word in picked]
    assert (books.count("a"), books.count("b")) == (3, 3)


def test_picks_are_spread_out_and_keep_each_books_order() -> None:
    assert mix([["a1", "a2", "a3"], ["b1", "b2"]], 4) == ["a1", "b1", "a2", "b2"]


def test_places_are_shared_in_equal_halves_and_a_short_book_leaves_its_spare() -> None:
    a = [f"a{i}" for i in range(80)]
    b = [f"b{i}" for i in range(30)]

    places = share_places([a, b], key=lambda word: word)[:100]
    assert (sum(w[0] == "a" for w in places), sum(w[0] == "b" for w in places)) == (70, 30)
    halves = share_places([a, [f"b{i}" for i in range(60)]], key=lambda word: word)[:100]
    assert (sum(w[0] == "a" for w in halves), sum(w[0] == "b" for w in halves)) == (50, 50)


def test_a_single_book_is_read_in_order() -> None:
    assert mix([["a1", "a2", "a3"]], 2) == ["a1", "a2"]


def test_an_exhausted_book_hands_its_slots_to_the_others() -> None:
    assert mix([["a1"], ["b1", "b2", "b3"]], 4) == ["a1", "b1", "b2", "b3"]


def test_a_word_shared_by_two_books_is_taken_once() -> None:
    picked = mix([["spleen", "purse"], ["spleen", "loom"]], 3)

    assert sorted(picked) == ["loom", "purse", "spleen"]


def test_stops_when_every_book_runs_out() -> None:
    assert mix([["a1"], []], 5) == ["a1"]
    assert mix([], 5) == []


def test_reading_a_chapter_suggests_it_and_the_next_two() -> None:
    assert suggested_chapters(4, 20) == [4, 5, 6]
    assert suggested_chapters(19, 20) == [19]
    assert suggested_chapters(0, 0) == [0]


def test_chosen_chapters_win_and_vanished_ones_are_dropped() -> None:
    assert reading_chapters([7, 2, 2], current=0, total=10) == [2, 7]
    assert reading_chapters([12], current=3, total=10) == [3, 4, 5]  # none left: suggest
    assert reading_chapters([], current=8, total=10) == [8, 9]
