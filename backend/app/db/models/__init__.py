"""All ORM models. Importing this package registers every table on Base.metadata."""

from app.db.models.learning import (
    CurrentReading,
    QuestClaim,
    Question,
    QuizAnswer,
    ShopPurchase,
    UserWord,
)
from app.db.models.library import Chapter, ChapterWord, Definition, Document, DocumentWord, Word
from app.db.models.reminders import PushSubscription, Reminder
from app.db.models.users import AuthSession, EmailToken, Friendship, GoalChange, User

__all__ = [
    "AuthSession",
    "Chapter",
    "ChapterWord",
    "CurrentReading",
    "Definition",
    "Document",
    "DocumentWord",
    "EmailToken",
    "Friendship",
    "GoalChange",
    "PushSubscription",
    "QuestClaim",
    "Question",
    "QuizAnswer",
    "Reminder",
    "ShopPurchase",
    "User",
    "UserWord",
    "Word",
]
