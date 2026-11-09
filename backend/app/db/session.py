from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import anyio
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

_SQLITE_IN_MEMORY = ("sqlite://", "sqlite:///:memory:")


def make_engine(database_url: str) -> Engine:
    if not database_url.startswith("sqlite"):
        return create_engine(database_url, pool_pre_ping=True)

    kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
    if database_url in _SQLITE_IN_MEMORY:
        kwargs["poolclass"] = StaticPool  # one shared connection, so the in-memory DB survives
    else:
        Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, **kwargs)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session_factory() -> sessionmaker[Session]:
    """FastAPI dependency for work that outlives the request (background tasks)."""
    return SessionLocal


async def get_session() -> AsyncIterator[Session]:
    """FastAPI dependency: one session per request, always closed.

    Async on purpose. FastAPI skips the cleanup of a plain (sync) generator dependency when the
    request is cancelled, e.g. the visitor's connection drops, so each cancelled request kept its
    database connection "idle in transaction" until the pool ran dry and every request hung. Here
    the session is closed in a `finally`, shielded from the cancellation, in a worker thread.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        with anyio.CancelScope(shield=True):
            await anyio.to_thread.run_sync(session.close)
