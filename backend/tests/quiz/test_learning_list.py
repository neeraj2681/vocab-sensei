from app.quiz.learning_list import mix_by_priority


def mix(queues: list[list[str]], count: int) -> list[str]:
    return mix_by_priority(queues, count, key=lambda word: word)


def test_three_books_share_slots_three_two_one() -> None:
    picked = mix([["a1", "a2", "a3", "a4"], ["b1", "b2", "b3"], ["c1", "c2"]], 6)

    books = [word[0] for word in picked]
    assert (books.count("a"), books.count("b"), books.count("c")) == (3, 2, 1)


def test_picks_are_spread_out_and_keep_each_books_order() -> None:
    assert mix([["a1", "a2", "a3"], ["b1", "b2"]], 4) == ["a1", "b1", "a2", "a3"]


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
