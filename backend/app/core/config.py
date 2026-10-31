"""Application settings, overridable with VOCAB_* environment variables or a .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = REPO_ROOT / "data"


class ScoringSettings(BaseModel):
    """Learning-score rules (see docs/PROJECT_PLAN.md §5.4)."""

    correct_delta: int = 5
    wrong_delta: int = -10
    learned_threshold: int = 100
    weekly_decay: int = 5
    unsure_start: int = 50
    floor: int = 0


class QuizSettings(BaseModel):
    """The never-ending quiz (docs/PROJECT_PLAN.md §5.3)."""

    options_per_question: int = Field(default=4, ge=2)
    spacing: int = Field(default=10, ge=0)  # a word isn't asked again within this many questions
    daily_goal: int = Field(default=10, gt=0)  # answers per day that keep the streak going
    # How often the next word is new / in progress / a learned word due for review (6:3:1).
    new_weight: int = Field(default=6, ge=0)
    learning_weight: int = Field(default=3, ge=0)
    review_weight: int = Field(default=1, ge=0)
    # "Similar difficulty" for wrong options: Zipf scores within this distance of the word's.
    distractor_zipf_window: float = Field(default=0.75, gt=0)
    # Question formats unlock as a word's score grows: reverse (meaning -> word), then also
    # fill-in-the-blank with the book's sentence.
    reverse_from_score: int = Field(default=30, ge=0)
    fill_from_score: int = Field(default=70, ge=0)


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

    @property
    def dictionary_dir(self) -> Path:
        return self.data_dir / "wordnet"


@lru_cache
def get_settings() -> Settings:
    return Settings()
