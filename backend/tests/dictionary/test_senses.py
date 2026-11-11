from app.dictionary.senses import best_sense, content_stems, rank_senses
from app.dictionary.types import Sense

ORGAN = Sense(
    "noun",
    "a large dark-red oval organ on the left side of the body between the stomach"
    " and the diaphragm",
    0,
)
ANGER = Sense("noun", "a feeling of resentful anger", 1, ("he vented his spleen on his opponent",))
SPLEEN = [ORGAN, ANGER]

MOBY = (
    "Whenever I find myself growing grim about the mouth; whenever it is a damp, drizzly"
    " November in my soul ... it is a way I have of driving off the spleen"
)


def test_no_overlap_keeps_the_default_sense() -> None:
    assert best_sense(MOBY, "spleen", SPLEEN) == 0


def test_overlap_picks_the_matching_sense() -> None:
    sentence = "She vented her spleen in a furious letter of resentful anger"
    assert rank_senses(sentence, "spleen", SPLEEN) == [1, 0]
    assert best_sense(sentence, "spleen", SPLEEN) == 1


def test_ties_keep_input_order() -> None:
    senses = [Sense("noun", "a red thing", 0), Sense("noun", "a red object", 1)]
    assert rank_senses("the red box", "box", senses) == [0, 1]
    assert best_sense("the red box", "box", senses) == 0


def test_the_lemma_never_counts() -> None:
    senses = [Sense("noun", "something", 0), Sense("noun", "the spleen organ", 1)]
    assert best_sense("her spleen", "spleen", senses) == 0


def test_content_stems() -> None:
    assert content_stems("The running dogs barked loudly") == {"runn", "dog", "bark", "loud"}


def test_empty_senses() -> None:
    assert best_sense("anything", "word", []) is None
    assert rank_senses("anything", "word", []) == []
