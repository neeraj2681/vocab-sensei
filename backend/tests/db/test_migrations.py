from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings
from app.db.base import Base

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture
def alembic_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Config]:
    monkeypatch.setenv("VOCAB_DATABASE_URL", f"sqlite:///{tmp_path / 'migrations.db'}")
    get_settings.cache_clear()
    yield Config(str(BACKEND_DIR / "alembic.ini"))
    get_settings.cache_clear()


def test_migrations_create_every_model_table_and_roll_back(alembic_config: Config) -> None:
    url = get_settings().database_url

    command.upgrade(alembic_config, "head")
    tables = set(inspect(create_engine(url)).get_table_names())
    assert set(Base.metadata.tables) <= tables

    command.check(alembic_config)  # fails if models changed without a new migration

    command.downgrade(alembic_config, "base")
    assert set(inspect(create_engine(url)).get_table_names()) == {"alembic_version"}
