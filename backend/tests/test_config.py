import pytest

from app.core.config import Settings


def test_scoring_defaults_match_plan() -> None:
    scoring = Settings().scoring

    assert (scoring.correct_delta, scoring.wrong_delta) == (5, -10)
    assert scoring.learned_threshold == 100
    assert scoring.weekly_decay == 5
    assert scoring.unsure_start == 50
    assert scoring.floor == 0


def test_settings_overridable_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOCAB_SCORING__CORRECT_DELTA", "7")
    monkeypatch.setenv("VOCAB_QUIZ__DAILY_GOAL", "5")

    settings = Settings()

    assert settings.scoring.correct_delta == 7
    assert settings.quiz.daily_goal == 5
