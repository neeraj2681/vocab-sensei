"""All ORM models. Importing this package registers every table on Base.metadata."""

from app.db.models.learning import CurrentReading, Question, QuizAnswer, UserWord
from app.db.models.library import Chapter, ChapterWord, Definition, Document, DocumentWord, Word
from app.db.models.reminders import PushSubscription, Reminder
from app.db.models.users import AuthSession, EmailToken, GoalChange, User

__all__ = [
    "AuthSession",
    "Chapter",
    "ChapterWord",
    "CurrentReading",
    "Definition",
    "Document",
    "DocumentWord",
    "EmailToken",
    "GoalChange",
    "PushSubscription",
    "Question",
    "QuizAnswer",
    "Reminder",
    "User",
    "UserWord",
    "Word",
]
