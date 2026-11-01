import os

# No background reminder thread in tests; they call ReminderService.send_due directly.
os.environ.setdefault("VOCAB_REMINDERS__SCHEDULER_ENABLED", "false")

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.api import rate_limit
from app.api.deps import get_dictionary, get_email_sender
from app.core import security
from app.core.config import Settings, get_settings
from app.core.email import Email
from app.db import models  # noqa: F401  registers every table
from app.db.base import Base
from app.db.models import User
from app.db.session import get_session, get_session_factory, make_engine
from app.db.types import utcnow
from app.dictionary.types import Sense
from app.main import create_app

TEST_PASSWORD = "correct horse battery"


class FakeEmailSender:
    def __init__(self) -> None:
        self.outbox: list[Email] = []

    def send(self, email: Email) -> None:
        self.outbox.append(email)


class FakeDictionary:
    """Knows every word except those in `unknown`; each has one noun sense, "meaning of <word>"."""

    source = "fake:1"

    def __init__(self) -> None:
        self.unknown: set[str] = set()
        self.entries: dict[str, list[Sense]] = {}  # replaces the default sense for these words
        self.synonym_sets: dict[str, frozenset[str]] = {}
        self.lookups: list[str] = []

    def senses(self, lemma: str) -> list[Sense]:
        self.lookups.append(lemma)
        if lemma in self.unknown:
            return []
        default = [Sense(pos="noun", definition=f"meaning of {lemma}", rank=0)]
        return self.entries.get(lemma, default)

    def synonyms(self, lemma: str) -> frozenset[str]:
        return self.synonym_sets.get(lemma, frozenset())


@pytest.fixture(autouse=True)
def fresh_rate_limits() -> None:
    """Request counts are kept in memory for the whole process; each test starts from zero."""
    rate_limit.reset()


# Tests use a fresh in-memory SQLite database each; CI also runs them against PostgreSQL by
# setting VOCAB_TEST_DATABASE_URL (e.g. postgresql+psycopg://vocab:vocab@localhost/vocab_test).
TEST_DATABASE_URL = os.environ.get("VOCAB_TEST_DATABASE_URL", "sqlite://")


@pytest.fixture(scope="session")
def server_engine() -> Iterator[Engine | None]:
    """One PostgreSQL engine and schema for the whole run (None when testing on SQLite)."""
    if TEST_DATABASE_URL.startswith("sqlite"):
        yield None
        return
    engine = make_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def engine(server_engine: Engine | None) -> Iterator[Engine]:
    """An empty database per test."""
    if server_engine is None:
        engine = make_engine("sqlite://")
        Base.metadata.create_all(engine)
        yield engine
        engine.dispose()
        return
    yield server_engine
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with server_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as s:
        yield s


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture
def mailer() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def dictionary() -> FakeDictionary:
    return FakeDictionary()


@pytest.fixture
def client(
    session: Session,
    session_factory: sessionmaker[Session],
    settings: Settings,
    mailer: FakeEmailSender,
    dictionary: FakeDictionary,
) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_email_sender] = lambda: mailer
    app.dependency_overrides[get_dictionary] = lambda: lambda: dictionary
    with TestClient(app) as c:
        yield c


def make_user(session: Session, email: str = "reader@example.com") -> User:
    """A verified user, created directly in the database (faster than the sign-up flow)."""
    user = User(
        email=email,
        password_hash=security.hash_password(TEST_PASSWORD),
        display_name="Reader",
        email_verified_at=utcnow(),
        daily_goal=10,  # tests count to the original goal
    )
    session.add(user)
    session.commit()
    return user


def log_in(client: TestClient, email: str) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text


@pytest.fixture
def user_client(client: TestClient, session: Session) -> TestClient:
    """`client`, logged in as reader@example.com."""
    log_in(client, make_user(session).email)
    return client
