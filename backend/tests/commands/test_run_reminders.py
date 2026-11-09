import os
import signal
import threading
from pathlib import Path
from typing import Any

import pytest

from app.commands import run_reminders
from app.core.config import Settings


def test_runs_the_reminder_checks_until_docker_stops_it(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, tmp_path: Path
) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setattr(run_reminders, "get_settings", lambda: settings)
    seen: dict[str, Any] = {}

    def fake_scheduler(stop: threading.Event, *args: object) -> None:
        seen["args"] = args
        os.kill(os.getpid(), signal.SIGTERM)  # what `docker compose stop` sends
        seen["stopped"] = stop.wait(timeout=5)

    monkeypatch.setattr(run_reminders, "run_scheduler", fake_scheduler)
    previous = signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)
    try:
        run_reminders.main()
    finally:
        signal.signal(signal.SIGTERM, previous[0])
        signal.signal(signal.SIGINT, previous[1])

    assert seen["stopped"] is True
    assert seen["args"][1] is settings
