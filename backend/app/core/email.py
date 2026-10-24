"""Sending email. Services depend on the EmailSender protocol, so tests can swap in a fake."""

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from app.core.config import EmailSettings


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    def send(self, email: Email) -> None: ...


class SmtpEmailSender:
    def __init__(self, settings: EmailSettings) -> None:
        self._settings = settings

    def send(self, email: Email) -> None:
        message = EmailMessage()
        message["From"] = self._settings.from_address
        message["To"] = email.to
        message["Subject"] = email.subject
        message.set_content(email.body)

        s = self._settings
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_username and s.smtp_password:
                smtp.login(s.smtp_username, s.smtp_password)
            smtp.send_message(message)
