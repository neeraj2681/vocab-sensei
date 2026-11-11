from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import DocumentFormat, PartOfSpeech
from app.db.models import Chapter, ChapterWord, Definition, Document, DocumentWord, Word
from app.dictionary.types import Sense
from app.extraction.words import Appearance, ExtractedWord
from app.services.words import WordService, _meaning_rank, definitions_in_context
from tests.conftest import FakeDictionary, make_user

SPLEEN_ORGAN = Sense(pos="noun", definition="an organ that filters the blood", rank=0)
SPLEEN_ANGER = Sense(
    pos="noun",
    definition="a feeling of resentful anger",
    rank=1,
    examples=("he vented his spleen on his opponent",),
)
ANGRY_SENTENCE = "She vented her spleen in a furious letter of resentful anger"


def test_meaning_rank_is_the_sense_the_sentence_uses() -> None:
    senses = [SPLEEN_ORGAN, SPLEEN_ANGER]

    assert _meaning_rank("spleen", PartOfSpeech.NOUN, ANGRY_SENTENCE, senses) == 1


def test_meaning_rank_is_none_without_a_clear_winner() -> None:
    senses = [SPLEEN_ORGAN, SPLEEN_ANGER]

    assert (
        _meaning_rank("spleen", PartOfSpeech.NOUN, "The weather was pleasant today", senses) is None
    )


def test_meaning_rank_is_none_without_a_part_of_speech() -> None:
    assert _meaning_rank("spleen", None, ANGRY_SENTENCE, [SPLEEN_ORGAN, SPLEEN_ANGER]) is None


def test_meaning_rank_is_none_without_senses_of_that_part_of_speech() -> None:
    assert (
        _meaning_rank("spleen", PartOfSpeech.VERB, ANGRY_SENTENCE, [SPLEEN_ORGAN, SPLEEN_ANGER])
        is None
    )


def test_definitions_in_context_put_the_sentence_meaning_first() -> None:
    word = Word(lemma="spleen")
    word.definitions = [
        Definition(pos="noun", text="organ", source="fake:1", sense_rank=0),
        Definition(pos="noun", text="anger", source="fake:1", sense_rank=1),
        Definition(pos="verb", text="to vent", source="fake:1", sense_rank=2),
    ]

    with_meaning = definitions_in_context(word, PartOfSpeech.NOUN, meaning_rank=1)
    without = definitions_in_context(word, PartOfSpeech.NOUN, meaning_rank=None)

    assert [d.sense_rank for d in with_meaning] == [1, 0, 2]
    assert [d.sense_rank for d in without] == [0, 1, 2]


def _document(session: Session) -> Document:
    document = Document(
        owner_user_id=make_user(session).id,
        title="Book",
        original_filename="book.epub",
        file_path="uploads/1/book.epub",
        format=DocumentFormat.EPUB,
        chapters=[Chapter(index=0), Chapter(index=1)],
    )
    session.add(document)
    session.flush()
    return document


def _spleen_in_two_chapters() -> ExtractedWord:
    # The first chapter uses the angry meaning, the second the organ (its first sense).
    return ExtractedWord(
        lemma="spleen",
        zipf=2.0,
        chapter_index=0,
        first_position=0,
        occurrences=2,
        context_sentence=ANGRY_SENTENCE,
        context_form="spleen",
        pos=PartOfSpeech.NOUN,
        appearances=(
            Appearance(0, 0, ANGRY_SENTENCE, "spleen"),
            Appearance(1, 5, "The spleen filters the blood.", "spleen"),
        ),
    )


def test_saving_stores_the_meaning_used_on_both_kinds_of_row(session: Session) -> None:
    dictionary = FakeDictionary()
    dictionary.entries["spleen"] = [SPLEEN_ORGAN, SPLEEN_ANGER]
    document = _document(session)

    WordService(session).save_for_document(document, [_spleen_in_two_chapters()], dictionary)

    book_row = session.scalars(select(DocumentWord)).one()
    assert book_row.meaning_rank == 1
    chapter_rows = dict(
        session.execute(
            select(Chapter.index, ChapterWord.meaning_rank).join(
                Chapter, Chapter.id == ChapterWord.chapter_id
            )
        ).all()
    )
    assert chapter_rows == {0: 1, 1: None}


def test_a_lemma_without_a_clear_winner_stores_none(session: Session) -> None:
    document = _document(session)
    bank = ExtractedWord(
        lemma="bank",
        zipf=2.0,
        chapter_index=0,
        first_position=0,
        occurrences=1,
        context_sentence="A bank sentence.",
        context_form="bank",
        pos=PartOfSpeech.NOUN,
    )

    WordService(session).save_for_document(document, [bank], FakeDictionary())

    assert session.scalars(select(DocumentWord.meaning_rank)).one() is None
    assert session.scalars(select(ChapterWord.meaning_rank)).one() is None


def test_chapter_mode_returns_the_meaning_of_that_chapters_sentence(session: Session) -> None:
    dictionary = FakeDictionary()
    dictionary.entries["spleen"] = [SPLEEN_ORGAN, SPLEEN_ANGER]
    document = _document(session)
    WordService(session).save_for_document(document, [_spleen_in_two_chapters()], dictionary)
    service = WordService(session)

    first_chapter = service.words_for_document(document, 0)
    second_chapter = service.words_for_document(document, 1)
    whole_book = service.words_for_document(document)

    assert [row[3:] for row in first_chapter] == [(ANGRY_SENTENCE, 1)]
    assert [row[3:] for row in second_chapter] == [("The spleen filters the blood.", None)]
    assert [row[4] for row in whole_book] == [1]  # the book row: the first appearance's meaning
