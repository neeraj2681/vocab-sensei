from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.api.documents import DefinitionResponse
from app.core.enums import PartOfSpeech
from app.db.session import get_session
from app.services.learning import LearningService
from app.services.words import definitions_in_context

router = APIRouter(prefix="/learning", tags=["learning"])


class LearningWordResponse(BaseModel):
    lemma: str
    pos: PartOfSpeech | None
    definitions: list[DefinitionResponse]  # the book's part of speech first
    context_sentence: str | None
    document_id: int
    document_title: str
    chapter_index: int
    chapter_title: str | None
    earlier: bool  # from a chapter before the one being read


@router.get("/next")
def next_words(
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
    count: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[LearningWordResponse]:
    """The next new words to learn, shared between current reads by priority."""
    return [
        LearningWordResponse(
            lemma=item.word.lemma,
            pos=item.occurrence.pos,
            definitions=[
                DefinitionResponse.model_validate(d)
                for d in definitions_in_context(item.word, item.occurrence.pos)
            ],
            context_sentence=item.occurrence.context_sentence,
            document_id=item.document.id,
            document_title=item.document.title,
            chapter_index=item.chapter.index,
            chapter_title=item.chapter.title,
            earlier=item.earlier,
        )
        for item in LearningService(session).next_new_words(user.id, count)
    ]
