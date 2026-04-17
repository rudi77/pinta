"""Minimal SMTP email service.

Wraps stdlib `smtplib` in `asyncio.to_thread` so callers can `await` from
request handlers without blocking the event loop. If SMTP is not configured
(empty `smtp_host`) the service no-ops with a WARNING log, so local
development without a mail server still boots.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from src.core.settings import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Async wrapper around stdlib smtplib for transactional email."""

    def __init__(self, cfg=settings) -> None:
        self.cfg = cfg

    @property
    def configured(self) -> bool:
        return bool(self.cfg.smtp_host and (self.cfg.smtp_from or self.cfg.smtp_user))

    @property
    def _from_address(self) -> str:
        address = self.cfg.smtp_from or self.cfg.smtp_user
        if self.cfg.smtp_from_name:
            return f"{self.cfg.smtp_from_name} <{address}>"
        return address

    async def send_email(
        self,
        to: str,
        subject: str,
        text_body: str,
        html_body: Optional[str] = None,
    ) -> bool:
        """Send an email; returns True if dispatched, False on no-op/failure."""
        if not self.configured:
            logger.warning(
                "SMTP not configured - skipping email to %s (subject=%r)",
                to, subject,
            )
            return False

        msg = EmailMessage()
        msg["From"] = self._from_address
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text_body)
        if html_body:
            msg.add_alternative(html_body, subtype="html")

        try:
            await asyncio.to_thread(self._send_sync, msg)
            logger.info("Email sent to %s (subject=%r)", to, subject)
            return True
        except Exception:
            logger.exception("Failed to send email to %s (subject=%r)", to, subject)
            return False

    def _send_sync(self, msg: EmailMessage) -> None:
        cfg = self.cfg
        if cfg.smtp_port == 465:
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=15) as smtp:
                if cfg.smtp_user:
                    smtp.login(cfg.smtp_user, cfg.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15) as smtp:
                if cfg.smtp_use_tls:
                    smtp.starttls()
                if cfg.smtp_user:
                    smtp.login(cfg.smtp_user, cfg.smtp_password)
                smtp.send_message(msg)

    async def send_verification_email(self, to: str, verification_url: str) -> bool:
        subject = "Bitte bestätige deine E-Mail-Adresse"
        text = (
            "Willkommen bei Pinta!\n\n"
            "Um dein Konto zu aktivieren, öffne bitte diesen Link:\n\n"
            f"{verification_url}\n\n"
            "Der Link ist 24 Stunden gültig. Falls du dich nicht registriert hast, "
            "kannst du diese E-Mail ignorieren."
        )
        html = (
            "<p>Willkommen bei Pinta!</p>"
            "<p>Um dein Konto zu aktivieren, klicke bitte auf diesen Link:</p>"
            f'<p><a href="{verification_url}">{verification_url}</a></p>'
            "<p>Der Link ist 24 Stunden gültig. Falls du dich nicht registriert hast, "
            "kannst du diese E-Mail ignorieren.</p>"
        )
        return await self.send_email(to, subject, text, html)


email_service = EmailService()
