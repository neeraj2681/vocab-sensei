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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VOCAB_", env_nested_delimiter="__", env_file=".env", extra="ignore"
    )

    data_dir: Path = DEFAULT_DATA_DIR
    database_url: str = f"sqlite:///{DEFAULT_DATA_DIR / 'vocab_sensei.db'}"
    scoring: ScoringSettings = ScoringSettings()
    quiz: QuizSettings = QuizSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
