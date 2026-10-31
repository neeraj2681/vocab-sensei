from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import DocumentFormat, PartOfSpeech
from app.db.models import Chapter, Document, Word
from app.extraction.words import ExtractedWord
from app.services.words import WordService
from tests.conftest import FakeDictionary, make_user


def make_document(session: Session, owner_email: str = "reader@example.com") -> Document:
    document = Document(
        owner_user_id=make_user(session, owner_email).id,
        title="Book",
        original_filename="book.epub",
        file_path="uploads/1/book.epub",
        format=DocumentFormat.EPUB,
        chapters=[Chapter(index=0)],
    )
    session.add(document)
    session.flush()
    return document


def extracted(lemma: str) -> ExtractedWord:
    return ExtractedWord(
        lemma=lemma,
        zipf=2.0,
        chapter_index=0,
        first_position=0,
        occurrences=1,
        context_sentence=f"A {lemma} sentence.",
        context_form=lemma,
        pos=PartOfSpeech.NOUN,
    )


def test_known_words_are_not_looked_up_again(session: Session) -> None:
    dictionary = FakeDictionary()
    service = WordService(session)
    service.save_for_document(make_document(session), [extracted("spleen")], dictionary)
    dictionary.lookups.clear()

    second = make_document(session, "second@example.com")
    service.save_for_document(second, [extracted("spleen")], dictionary)

    assert dictionary.lookups == []


def test_words_stored_without_definitions_are_looked_up(session: Session) -> None:
    session.add(Word(lemma="spleen", zipf_frequency=3.1))  # saved before definitions existed
    session.flush()

    WordService(session).save_for_document(
        make_document(session), [extracted("spleen")], FakeDictionary()
    )

    word = session.scalars(select(Word).where(Word.lemma == "spleen")).one()
    assert [d.text for d in word.definitions] == ["meaning of spleen"]
    assert word.definitions[0].source == "fake:1"
