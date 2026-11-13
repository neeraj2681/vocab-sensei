"""Application settings, overridable with VOCAB_* environment variables or a .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = REPO_ROOT / "data"


class ScoringSettings(BaseModel):
    """Learning-score rules (see docs/PROJECT_PLAN.md §5.4)."""

    correct_delta: int = 5  # coins for a right answer
    word_correct_delta: int = 10  # a right answer's step towards "learned": 10 right answers
    wrong_delta: int = -5  # a miss, for words and coins alike...
    # ...but a miss on a word learned before (reached `learned_threshold`) costs this while its
    # score is above `review_strict_above`; at or below it, misses are back to `wrong_delta`.
    review_wrong_delta: int = -10
    review_strict_above: int = 50
    learned_threshold: int = 100
    weekly_decay: int = 5  # a learned word loses this per week once its review is due...
    # ...but never below `review_strict_above`. Its gap between reviews starts at 1 week, doubles
    # after each review that was due (up to this), and halves after a miss.
    max_interval_weeks: int = 16
    unsure_start: int = 50
    floor: int = 0
    # Ninja Mode: after `combo_after` right answers in a row, right answers earn `combo_multiplier`
    # times the coins until a wrong one (or the player stops after a session).
    combo_after: int = 5
    combo_multiplier: int = 2


class QuizSettings(BaseModel):
    """The never-ending quiz (docs/PROJECT_PLAN.md §5.3)."""

    options_per_question: int = Field(default=4, ge=2)
    spacing: int = Field(default=10, ge=0)  # a word isn't asked again within this many questions
    retry_after: int = Field(default=3, ge=0)  # ...unless answered wrong: then after this many
    # Words in progress at once (new ones wait): the user's daily goal, kept within these bounds.
    # The smallest stays above `spacing`, or the quiz would run out of words it may ask.
    learning_cap_min: int = Field(default=15, ge=1)
    learning_cap_max: int = Field(default=50, ge=1)
    daily_goal: int = Field(default=20, gt=0)  # new accounts' answers a day (about 5 minutes)
    # How often the next word is new / in progress / a learned word due for review (6:3:1).
    new_weight: int = Field(default=6, ge=0)
    learning_weight: int = Field(default=3, ge=0)
    review_weight: int = Field(default=1, ge=0)
    # Review gets one more turn per this many words due, up to `max_review_weight`, so a backlog
    # of learned words is caught up instead of fading.
    due_per_review_weight: int = Field(default=5, gt=0)
    max_review_weight: int = Field(default=6, ge=0)
    # "Similar difficulty" for wrong options: Zipf scores within this distance of the word's.
    distractor_zipf_window: float = Field(default=0.75, gt=0)
    # Question formats unlock as a word's score grows: reverse (meaning -> word), then also
    # fill-in-the-blank with the book's sentence.
    reverse_from_score: int = Field(default=30, ge=0)
    fill_from_score: int = Field(default=70, ge=0)
    # "Which meaning is used here?", for words whose sentence clearly picks one of several meanings
    meaning_from_score: int = Field(default=30, ge=0)


class AuthSettings(BaseModel):
    session_days: int = Field(default=30, gt=0)
    cookie_name: str = "vs_session"
    cookie_secure: bool = False  # set True when served over HTTPS
    verify_email_hours: int = Field(default=24, gt=0)
    reset_password_minutes: int = Field(default=60, gt=0)


class RateLimitSettings(BaseModel):
    """Limits per client address, in the `limits` notation ("10/minute", "5/hour;20/day")."""

    enabled: bool = True
    login: str = "10/minute;50/hour"
    email: str = "5/hour"  # sign-up, resend verification, forgot password: each sends an email
    # Where counts are kept: "memory://" for one process; "valkey://valkey:6379" (Valkey) when the
    # API runs several worker processes, so they share one count.
    storage_uri: str = "memory://"
    trust_proxy: bool = False  # True behind Cloudflare Tunnel (reads CF-Connecting-IP)


class EmailSettings(BaseModel):
    """SMTP settings. Defaults point at Mailpit, which catches emails locally."""

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = False
    from_address: str = "Vocab Sensei <no-reply@vocab-sensei.local>"
    app_base_url: str = "http://localhost:5173"  # links in emails point to the frontend


class UploadSettings(BaseModel):
    max_bytes: int = Field(default=50 * 1024 * 1024, gt=0)


class ExtractionSettings(BaseModel):
    """Which words count as worth learning (wordfreq Zipf scale: 7 = "the", 1 = very rare)."""

    max_zipf: float = 4.0  # more common than this is "already known" (e.g. "house" is 5.7)
    min_zipf: float = 1.0  # rarer than this is usually a typo, OCR noise or a made-up name
    min_length: int = 3
    context_chars: int = 300


class DictionarySettings(BaseModel):
    """Definitions come from Open English WordNet (https://en-word.net, CC BY 4.0)."""

    lexicon: str = "oewn:2025"
    senses_per_pos: int = Field(default=3, gt=0)  # e.g. at most 3 noun and 3 verb meanings


class PushSettings(BaseModel):
    """Web Push (VAPID). Leave the keys empty to have one pair created in the data directory."""

    vapid_private_key: str | None = None  # PEM
    vapid_public_key: str | None = None  # base64url
    subject: str = "mailto:no-reply@vocab-sensei.local"  # who to contact about our pushes


class ReminderSettings(BaseModel):
    scheduler_enabled: bool = True  # tests and one-off scripts turn it off
    check_seconds: int = Field(default=60, gt=0)


class LibrarySettings(BaseModel):
    """Built-in classics (see app/services/library.py)."""

    default_classic: int = 1342  # Project Gutenberg id new users start on (Pride and Prejudice)


class SpeechSettings(BaseModel):
    """Pronunciation practice: speech recognition on our own server (faster-whisper)."""

    model: str = "base.en"  # English Whisper, ~140 MB, about half a second a word on a laptop CPU
    model_dir: Path | None = None  # a model already downloaded (the Docker image has one)
    say_word_share: float = Field(default=0.2, ge=0, le=1)  # of well-known words in the quiz
    max_audio_bytes: int = 1_000_000
    pause_minutes: int = Field(default=10, gt=0)  # after "Can't speak right now"


class NewsletterSettings(BaseModel):
    """Brevo keeps the newsletter's mailing list; without a key and list nothing is sent there."""

    brevo_api_key: str | None = None  # Brevo: SMTP & API -> API Keys
    brevo_list_id: int | None = None  # Brevo: Contacts -> Lists -> the list's ID
    brevo_api_url: str = "https://api.brevo.com/v3"

    @field_validator("brevo_api_key", "brevo_list_id", mode="before")
    @classmethod
    def _empty_is_unset(cls, value: object) -> object:
        return None if value == "" else value  # `VOCAB_NEWSLETTER__BREVO_LIST_ID=` in .env


class JobSettings(BaseModel):
    """Background jobs (Celery). Without a broker, jobs run in the API process afterwards."""

    broker_url: str | None = None  # e.g. "redis://valkey:6379/1"

    @field_validator("broker_url", mode="before")
    @classmethod
    def _empty_is_unset(cls, value: object) -> object:
        return None if value == "" else value  # `VOCAB_JOBS__BROKER_URL=` in .env


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VOCAB_", env_nested_delimiter="__", env_file=".env", extra="ignore"
    )

    data_dir: Path = DEFAULT_DATA_DIR
    database_url: str = f"sqlite:///{DEFAULT_DATA_DIR / 'vocab_sensei.db'}"
    scoring: ScoringSettings = ScoringSettings()
    quiz: QuizSettings = QuizSettings()
    auth: AuthSettings = AuthSettings()
    rate_limit: RateLimitSettings = RateLimitSettings()
    email: EmailSettings = EmailSettings()
    upload: UploadSettings = UploadSettings()
    extraction: ExtractionSettings = ExtractionSettings()
    dictionary: DictionarySettings = DictionarySettings()
    push: PushSettings = PushSettings()
    reminders: ReminderSettings = ReminderSettings()
    library: LibrarySettings = LibrarySettings()
    speech: SpeechSettings = SpeechSettings()
    newsletter: NewsletterSettings = NewsletterSettings()
    jobs: JobSettings = JobSettings()

    @property
    def dictionary_dir(self) -> Path:
        return self.data_dir / "wordnet"


@lru_cache
def get_settings() -> Settings:
    return Settings()
