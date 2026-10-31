"""How ready the user is for each chapter of a book: the average progress of its words.

Every word that first appears in the chapter counts by its score toward 100: known and learned
words count fully (a learned word whose score decayed counts at its decayed score), a word at 40
counts 40 %, untouched words 0. So readiness moves with every right answer.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import ScoringSettings
from app.core.enums import WordStatus
from app.db.models import Document, UserWord
from app.repositories.learning import LearningRepository
from app.scoring.rules import WordProgress, effective_score


@dataclass(frozen=True)
class ChapterReadiness:
    index: int
    title: str | None
    words: int
    done: int  # learned or known
    in_progress: int
    new: int
    readiness: int  # 0-100


def word_progress(word: UserWord | None, now: datetime, rules: ScoringSettings) -> int:
    """0-100 for one word."""
    if word is None:
        return 0
    if word.status is WordStatus.KNOWN:
        return 100
    progress = WordProgress(score=word.score, status=word.status, learned_at=word.learned_at)
    threshold = max(rules.learned_threshold, 1)
    return min(effective_score(progress, now, rules), threshold) * 100 // threshold


class ReadinessService:
    def __init__(self, session: Session, rules: ScoringSettings) -> None:
        self._repo = LearningRepository(session)
        self._rules = rules

    def for_document(
        self, user_id: int, document: Document, now: datetime
    ) -> list[ChapterReadiness]:
        per_chapter: dict[int, list[int]] = defaultdict(list)
        for index, word in self._repo.progress_by_chapter(user_id, document.id):
            per_chapter[index].append(word_progress(word, now, self._rules))
        result = []
        for chapter in document.chapters:
            scores = per_chapter.get(chapter.index, [])
            done = sum(1 for p in scores if p >= 100)
            new = sum(1 for p in scores if p == 0)
            result.append(
                ChapterReadiness(
                    index=chapter.index,
                    title=chapter.title,
                    words=len(scores),
                    done=done,
                    in_progress=len(scores) - done - new,
                    new=new,
                    readiness=round(sum(scores) / len(scores)) if scores else 100,
                )
            )
        return result
