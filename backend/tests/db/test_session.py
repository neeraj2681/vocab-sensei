from collections.abc import AsyncGenerator
from pathlib import Path

import anyio
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.db import session as db_session


def test_a_cancelled_request_still_gives_its_connection_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A visitor's connection dropping cancels the request; the connection must not leak.
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(bind=engine))

    async def request_cancelled_midway() -> None:
        cancelled = anyio.get_cancelled_exc_class()  # asyncio.CancelledError
        dependency: AsyncGenerator[Session] = db_session.get_session()  # type: ignore[assignment]
        session = await dependency.__anext__()
        session.execute(text("select 1"))
        assert engine.pool.checkedout() == 1  # type: ignore[attr-defined]
        with pytest.raises(cancelled):
            await dependency.athrow(cancelled())

    anyio.run(request_cancelled_midway)

    assert engine.pool.checkedout() == 0  # type: ignore[attr-defined]
