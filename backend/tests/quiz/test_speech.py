import pytest

from app.quiz.speech import said


@pytest.mark.parametrize(
    ("heard", "word"),
    [
        ("Lugubrious.", "lugubrious"),
        ("Laguubrious.", "lugubrious"),  # nearly the same spelling
        ("Like Ubrius.", "lugubrious"),  # sounds the same
        ("Mel and Colley", "melancholy"),  # split into pieces
        ("ebullient.", "ebullient"),
    ],
)
def test_close_enough_counts(heard: str, word: str) -> None:
    assert said(heard, word)


@pytest.mark.parametrize(
    ("heard", "word"),
    [("Banana.", "lugubrious"), ("Serene", "ephemeral"), ("", "serene"), ("...", "serene")],
)
def test_other_words_and_silence_dont(heard: str, word: str) -> None:
    assert not said(heard, word)
