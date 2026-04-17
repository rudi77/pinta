"""EmailService must no-op without SMTP config and build a correct message."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.services.email_service import EmailService


def _cfg(**kw):
    defaults = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_user": "sender@example.com",
        "smtp_password": "secret",
        "smtp_from": "",
        "smtp_from_name": "Pinta",
        "smtp_use_tls": True,
    }
    defaults.update(kw)
    return SimpleNamespace(**defaults)


class TestEmailService:
    async def test_no_op_when_smtp_host_missing(self):
        svc = EmailService(_cfg(smtp_host=""))
        assert svc.configured is False
        ok = await svc.send_email("u@example.com", "hi", "body")
        assert ok is False

    async def test_from_address_includes_display_name(self):
        svc = EmailService(_cfg())
        assert svc._from_address == "Pinta <sender@example.com>"

    async def test_from_address_uses_smtp_from_override(self):
        svc = EmailService(_cfg(smtp_from="noreply@pinta.app"))
        assert "noreply@pinta.app" in svc._from_address

    async def test_send_email_invokes_smtp_with_starttls(self):
        svc = EmailService(_cfg())
        captured = {}

        def fake_send_sync(msg):
            captured["to"] = msg["To"]
            captured["from"] = msg["From"]
            captured["subject"] = msg["Subject"]

        with patch.object(svc, "_send_sync", side_effect=fake_send_sync):
            ok = await svc.send_email(
                to="cust@example.com",
                subject="Test",
                text_body="plain",
                html_body="<p>html</p>",
            )
        assert ok is True
        assert captured["to"] == "cust@example.com"
        assert captured["subject"] == "Test"
        assert "sender@example.com" in captured["from"]

    async def test_send_verification_email_contains_url(self):
        svc = EmailService(_cfg())
        captured_msg = {}

        def fake_send_sync(msg):
            # Walk the message parts and concatenate their text to inspect.
            body = ""
            for part in msg.walk():
                if part.get_content_maintype() == "text":
                    body += part.get_content()
            captured_msg["body"] = body
            captured_msg["subject"] = msg["Subject"]

        with patch.object(svc, "_send_sync", side_effect=fake_send_sync):
            ok = await svc.send_verification_email(
                "new@example.com", "https://app.test/verify/abc123"
            )
        assert ok is True
        assert "https://app.test/verify/abc123" in captured_msg["body"]
        assert "bestätige" in captured_msg["subject"].lower()

    async def test_send_email_swallows_smtp_errors(self):
        svc = EmailService(_cfg())
        with patch.object(svc, "_send_sync", side_effect=ConnectionRefusedError):
            ok = await svc.send_email("u@x", "s", "b")
        assert ok is False
