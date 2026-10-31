"""Enums shared across layers (domain modules and database models)."""

from enum import StrEnum


class WordStatus(StrEnum):
    NEW = "new"  # never answered
    LEARNING = "learning"
    LEARNED = "learned"  # score reached the threshold; decays weekly
    KNOWN = "known"  # user said they already know it; never quizzed


class PartOfSpeech(StrEnum):
    """The parts of speech we learn words for (names match dictionary definitions)."""

    NOUN = "noun"
    VERB = "verb"
    ADJECTIVE = "adjective"
    ADVERB = "adverb"


class DocumentFormat(StrEnum):
    EPUB = "epub"
    PDF = "pdf"
    TXT = "txt"

    @property
    def ext(self) -> str:
        return f".{self.value}"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class EmailTokenPurpose(StrEnum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"


class QuestionType(StrEnum):
    DEFINITION_MCQ = "definition_mcq"  # MVP
    FILL_IN_BLANK = "fill_in_blank"
    CORRECT_USAGE = "correct_usage"
    NUANCE = "nuance"
    REVERSE = "reverse"


class ReminderChannel(StrEnum):
    PUSH = "push"  # a notification on the devices where the user enabled it
    EMAIL = "email"
