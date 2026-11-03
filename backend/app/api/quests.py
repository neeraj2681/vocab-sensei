from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SettingsDep
from app.api.quiz import Now, TimeZone
from app.db.session import get_session
from app.services.quests import (
    AlreadyClaimedError,
    DailyQuests,
    QuestNotDoneError,
    QuestService,
    UnknownQuestError,
)

router = APIRouter(prefix="/quests", tags=["quests"])


def get_quest_service(
    session: Annotated[Session, Depends(get_session)], settings: SettingsDep
) -> QuestService:
    return QuestService(session, settings)


QuestServiceDep = Annotated[QuestService, Depends(get_quest_service)]


class QuestResponse(BaseModel):
    key: str
    kind: str
    tier: str  # easy / medium / hard
    title: str
    target: int
    progress: int
    reward: int
    claimed: bool


class DailyQuestsResponse(BaseModel):
    quests: list[QuestResponse]
    chest_reward: int  # for claiming all three
    chest_ready: bool
    chest_claimed: bool

    @classmethod
    def of(cls, daily: DailyQuests) -> Self:
        return cls(
            quests=[
                QuestResponse(
                    key=s.quest.key,
                    kind=s.quest.kind.value,
                    tier=s.quest.tier.value,
                    title=s.quest.title,
                    target=s.quest.target,
                    progress=s.progress,
                    reward=s.quest.reward,
                    claimed=s.claimed,
                )
                for s in daily.quests
            ],
            chest_reward=daily.chest_reward,
            chest_ready=daily.chest_ready,
            chest_claimed=daily.chest_claimed,
        )


class ClaimResponse(BaseModel):
    coins: int  # just added
    total: int  # lifetime coins now
    quests: DailyQuestsResponse


@router.get("")
def today(
    user: CurrentUser, quests: QuestServiceDep, now: Now, tz: TimeZone
) -> DailyQuestsResponse:
    """Today's three quests (one easy, one medium, one hard) with their progress."""
    return DailyQuestsResponse.of(quests.today(user.id, now, tz))


@router.post("/{key}/claim")
def claim(
    key: str, user: CurrentUser, quests: QuestServiceDep, now: Now, tz: TimeZone
) -> ClaimResponse:
    """Collects a finished quest's coins; "chest" opens the bonus once all three are claimed."""
    try:
        coins = quests.claim(user.id, key, now, tz)
    except UnknownQuestError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from None
    except AlreadyClaimedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except QuestNotDoneError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return ClaimResponse(
        coins=coins,
        total=quests.total(user.id),
        quests=DailyQuestsResponse.of(quests.today(user.id, now, tz)),
    )
