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
    round_size: int = Field(default=10, gt=0)
    options_per_question: int = Field(default=4, ge=2)


class AuthSettings(BaseModel):
    session_days: int = Field(default=30, gt=0)
    cookie_name: str = "vs_session"
    cookie_secure: bool = False  # set True when served over HTTPS
    verify_email_hours: int = Field(default=24, gt=0)
    reset_password_minutes: int = Field(default=60, gt=0)


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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VOCAB_", env_nested_delimiter="__", env_file=".env", extra="ignore"
    )

    data_dir: Path = DEFAULT_DATA_DIR
    database_url: str = f"sqlite:///{DEFAULT_DATA_DIR / 'vocab_sensei.db'}"
    scoring: ScoringSettings = ScoringSettings()
    quiz: QuizSettings = QuizSettings()
    auth: AuthSettings = AuthSettings()
    email: EmailSettings = EmailSettings()
    upload: UploadSettings = UploadSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
