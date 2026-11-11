import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.commands import reindex_meanings
from app.core.config import Settings
from app.core.enums import DocumentFormat, DocumentStatus, PartOfSpeech
from app.db.models import Chapter, ChapterWord, Document, DocumentWord
from app.dictionary.types import Sense
from app.extraction.words import Appearance, ExtractedWord
from app.services.words import WordService
from tests.conftest import FakeDictionary, make_user

SPLEEN_ORGAN = Sense(pos="noun", definition="an organ that filters the blood", rank=0)
SPLEEN_ANGER = Sense(pos="noun", definition="a feeling of resentful anger", rank=1)
ANGRY_SENTENCE = "She vented her spleen in a furious letter of resentful anger"
PLAIN_SENTENCE = "The weather was pleasant today"


def _dictionary() -> FakeDictionary:
    dictionary = FakeDictionary()
    dictionary.entries["spleen"] = [SPLEEN_ORGAN, SPLEEN_ANGER]
    return dictionary


def _document(session: Session, status: DocumentStatus, title: str) -> Document:
    document = Document(
        owner_user_id=make_user(session, email=f"{title}@example.com").id,
        title=title,
        original_filename="book.epub",
        file_path="uploads/1/book.epub",
        format=DocumentFormat.EPUB,
        status=status,
        chapters=[Chapter(index=0)],
    )
    session.add(document)
    session.flush()
    return document


def _word(lemma: str, sentence: str) -> ExtractedWord:
    return ExtractedWord(
        lemma=lemma,
        zipf=2.0,
        chapter_index=0,
        first_position=0,
        occurrences=1,
        context_sentence=sentence,
        context_form=lemma,
        pos=PartOfSpeech.NOUN,
        appearances=(Appearance(0, 0, sentence, lemma),),
    )


def _store_without_meanings(
    session: Session, document: Document, words: list[ExtractedWord]
) -> None:
    """Saves the words the way a book processed before meanings were stored has them."""
    WordService(session).save_for_document(document, words, _dictionary())
    session.execute(update(DocumentWord).values(meaning_rank=None))
    session.execute(update(ChapterWord).values(meaning_rank=None))
    session.flush()


def _run(
    session_factory: sessionmaker[Session], settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> int:
    dictionary = _dictionary()
    monkeypatch.setattr(reindex_meanings, "get_dictionary", lambda _settings: lambda: dictionary)
    return reindex_meanings.reindex(session_factory, settings)


def test_fills_in_the_meaning_for_a_ready_book_and_is_idempotent(
    session: Session,
    session_factory: sessionmaker[Session],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _document(session, DocumentStatus.READY, "Old Book")
    _store_without_meanings(session, document, [_word("spleen", ANGRY_SENTENCE)])
    session.commit()

    assert _run(session_factory, settings, monkeypatch) == 2

    session.expire_all()
    assert session.scalars(select(DocumentWord.meaning_rank)).one() == 1
    assert session.scalars(select(ChapterWord.meaning_rank)).one() == 1
    assert _run(session_factory, settings, monkeypatch) == 0


def test_a_sentence_without_a_clear_winner_stays_none(
    session: Session,
    session_factory: sessionmaker[Session],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _document(session, DocumentStatus.READY, "Plain Book")
    _store_without_meanings(session, document, [_word("spleen", PLAIN_SENTENCE)])
    session.commit()

    assert _run(session_factory, settings, monkeypatch) == 0

    session.expire_all()
    assert session.scalars(select(DocumentWord.meaning_rank)).one() is None
    assert session.scalars(select(ChapterWord.meaning_rank)).one() is None


def test_a_book_that_is_not_ready_is_skipped(
    session: Session,
    session_factory: sessionmaker[Session],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _document(session, DocumentStatus.PROCESSING, "Still Processing")
    _store_without_meanings(session, document, [_word("spleen", ANGRY_SENTENCE)])
    session.commit()

    assert _run(session_factory, settings, monkeypatch) == 0

    session.expire_all()
    assert session.scalars(select(DocumentWord.meaning_rank)).one() is None
    assert session.scalars(select(ChapterWord.meaning_rank)).one() is None
