import pytest

from app.core.config import ExtractionSettings
from app.core.enums import PartOfSpeech
from app.extraction.types import ParsedChapter
from app.extraction.words import ExtractedWord, WordExtractor


def extract(*texts: str, **settings: float) -> list[ExtractedWord]:
    chapters = [ParsedChapter(title=None, text=text) for text in texts]
    return WordExtractor(ExtractionSettings(**settings)).extract(chapters)


def lemmas(words: list[ExtractedWord]) -> list[str]:
    return [w.lemma for w in words]


def test_keeps_rare_words_and_reduces_them_to_their_lemma() -> None:
    words = extract("The lugubrious sailors were perambulating along the docks.")

    assert "lugubrious" in lemmas(words)
    assert "perambulate" in lemmas(words)  # from "perambulating"


def test_drops_common_words_stopwords_and_names() -> None:
    words = extract("Ishmael walked into the big house with his friend Queequeg.")

    assert lemmas(words) == []


@pytest.mark.parametrize("text", ["It was 1851.", "Hmm... ok?!", ""])
def test_ignores_numbers_punctuation_and_empty_text(text: str) -> None:
    assert extract(text) == []


def test_records_first_chapter_position_count_and_sentence() -> None:
    words = extract(
        "Nothing rare here.\nA lugubrious tune played.",
        "The tune remained lugubrious all night.",
    )

    [word] = [w for w in words if w.lemma == "lugubrious"]
    assert word.chapter_index == 0
    assert word.first_position == 5  # "Nothing rare here ." is 4 tokens, then "A" is 4
    assert word.occurrences == 2
    assert word.context_sentence == "A lugubrious tune played."
    assert word.context_form == "lugubrious"
    assert 1.0 <= word.zipf < 4.0


def test_words_come_in_reading_order() -> None:
    words = extract("A perfunctory nod.", "An obsequious bow, then another perfunctory nod.")

    rare = [w for w in words if w.lemma in {"perfunctory", "obsequious"}]
    assert [(w.lemma, w.chapter_index) for w in rare] == [("perfunctory", 0), ("obsequious", 1)]


def test_thresholds_come_from_settings() -> None:
    text = "A lugubrious tune played in the house."

    assert "house" not in lemmas(extract(text))
    assert "house" in lemmas(extract(text, max_zipf=6.0))
    assert "lugubrious" not in lemmas(extract(text, min_zipf=3.0))


def test_long_sentences_are_trimmed_around_the_word() -> None:
    filler = "and then the ship sailed on " * 20
    words = extract(f"It began {filler} until a lugubrious silence {filler} fell.")

    [word] = [w for w in words if w.lemma == "lugubrious"]
    assert len(word.context_sentence) <= 302  # 300 plus the two ellipses
    assert "lugubrious" in word.context_sentence
    assert word.context_sentence.startswith("…")
    assert word.context_sentence.endswith("…")


def test_records_how_the_book_uses_each_word() -> None:
    words = extract(
        "The sailors were perambulating slowly.",
        "It was a damp morning. The damp cellar smelled of the sea.",
    )

    pos = {w.lemma: w.pos for w in words}
    assert pos["perambulate"] == PartOfSpeech.VERB
    assert pos["damp"] == PartOfSpeech.ADJECTIVE


def test_remembers_the_form_used_in_the_sentence() -> None:
    [word] = [
        w
        for w in extract("The sailors were perambulating along the docks.")
        if w.lemma == "perambulate"
    ]

    assert word.context_form == "perambulating"
