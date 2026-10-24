from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_email_sender
from app.core.email import Email
from app.db import models  # noqa: F401  registers every table
from app.db.base import Base
from app.db.session import get_session, make_engine
from app.main import create_app


class FakeEmailSender:
    def __init__(self) -> None:
        self.outbox: list[Email] = []

    def send(self, email: Email) -> None:
        self.outbox.append(email)


@pytest.fixture
def session() -> Iterator[Session]:
    """A fresh in-memory database per test."""
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s
    engine.dispose()


@pytest.fixture
def mailer() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def client(session: Session, mailer: FakeEmailSender) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_email_sender] = lambda: mailer
    with TestClient(app) as c:
        yield c
