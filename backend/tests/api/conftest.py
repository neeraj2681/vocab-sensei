"""Fixtures shared by the API tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import DocumentFormat, DocumentStatus, PartOfSpeech
from app.db.models import Chapter, CurrentReading, Document, DocumentWord
from tests.api.test_quiz import LEMMAS, add_word, reader

# Two chapters: word00-word09 in the first, word10-word19 in the second.
CHAPTER_OF = {lemma: 0 if i < 10 else 1 for i, lemma in enumerate(LEMMAS)}


@pytest.fixture
def two_chapter_book(user_client: TestClient, session: Session) -> Document:
    """A ready book being read by reader@example.com: word00-word09 in chapter 0, word10-19 in 1."""
    user = reader(session)
    document = Document(
        owner_user_id=user.id,
        title="Moby-Dick",
        original_filename="moby.epub",
        file_path="uploads/1/moby.epub",
        format=DocumentFormat.EPUB,
        status=DocumentStatus.READY,
        chapters=[Chapter(index=0, title="Loomings"), Chapter(index=1, title="The Carpet-Bag")],
    )
    session.add(document)
    session.flush()
    for position, lemma in enumerate(LEMMAS):
        word = add_word(session, lemma)
        session.add(
            DocumentWord(
                document_id=document.id,
                word_id=word.id,
                chapter_id=document.chapters[CHAPTER_OF[lemma]].id,
                first_position=position,
                context_sentence=f"A sentence with {lemma}.",
                pos=PartOfSpeech.NOUN,
            )
        )
    session.add(CurrentReading(user_id=user.id, document_id=document.id))
    session.commit()
    return document
