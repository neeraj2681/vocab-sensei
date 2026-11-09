"""Runs the daily-reminder checks as a process of its own.

    uv run python -m app.commands.run_reminders

The API normally runs these checks in a background thread. When it runs as several worker
processes, each would start that thread and people would get the same reminder several times, so
deployments switch the thread off (VOCAB_REMINDERS__SCHEDULER_ENABLED=false) and run this instead.
Stops cleanly on Ctrl+C or `docker compose stop`.
"""

import logging
import signal
import threading

from app.core.config import get_settings
from app.core.email import SmtpEmailSender
from app.core.push import WebPushSender, load_or_create_keys
from app.db.session import SessionLocal
from app.services.reminders import run_scheduler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    push = WebPushSender(
        load_or_create_keys(settings.push, settings.data_dir), settings.push.subject
    )
    logging.getLogger(__name__).info("reminder checks started")
    run_scheduler(stop, SessionLocal, settings, SmtpEmailSender(settings.email), push)


if __name__ == "__main__":
    main()
