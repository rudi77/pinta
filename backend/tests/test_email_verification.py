"""End-to-end tests for the email verification flow (Blocker #2)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.core.security import get_password_hash
from src.models.models import EmailVerificationToken, User


async def _make_user(session, *, email: str, verified: bool) -> User:
    user = User(
        email=email,
        username=email.split("@")[0] + "-u",
        hashed_password=get_password_hash("StrongPass123!"),
        is_active=True,
        is_verified=verified,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


class TestRegistrationIssuesVerification:
    async def test_registration_sends_verification_email_in_production(
        self, client: AsyncClient, test_session
    ):
        """In production mode, registering a user creates a pending token and
        attempts to email the verification link. The user is NOT verified yet."""
        send_mock = AsyncMock(return_value=True)
        with patch(
            "src.routes.auth.email_service.send_verification_email", send_mock
        ), patch("src.routes.auth.settings.debug", False):
            payload = {
                "email": "newcustomer@example.com",
                "username": "newcustomer",
                "password": "StrongPass123!",
                "company_name": "New GmbH",
                "phone": "+49123",
                "address": "Street 1",
            }
            resp = await client.post("/api/v1/auth/register", json=payload)

        assert resp.status_code == 201, resp.text
        assert resp.json()["is_verified"] is False

        send_mock.assert_awaited_once()
        to_arg, url_arg = send_mock.await_args.args
        assert to_arg == "newcustomer@example.com"
        assert "/verify-email?token=" in url_arg

        # Token row persisted
        tokens = (
            await test_session.execute(select(EmailVerificationToken))
        ).scalars().all()
        assert len(tokens) == 1
        assert tokens[0].used_at is None


class TestLoginGate:
    async def test_unverified_user_cannot_login(
        self, client: AsyncClient, test_session
    ):
        await _make_user(test_session, email="unv@example.com", verified=False)
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "unv@example.com", "password": "StrongPass123!"},
        )
        assert resp.status_code == 403
        assert "not verified" in resp.json()["detail"].lower()


class TestVerifyEmailEndpoint:
    async def test_happy_path_marks_user_verified_and_token_used(
        self, client: AsyncClient, test_session
    ):
        user = await _make_user(test_session, email="v@example.com", verified=False)
        token = EmailVerificationToken(
            user_id=user.id,
            token="valid-token-xyz",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        test_session.add(token)
        await test_session.commit()

        resp = await client.get("/api/v1/auth/verify-email?token=valid-token-xyz")
        assert resp.status_code == 200

        await test_session.refresh(user)
        assert user.is_verified is True

        refreshed_token = (
            await test_session.execute(
                select(EmailVerificationToken).where(
                    EmailVerificationToken.id == token.id
                )
            )
        ).scalar_one()
        assert refreshed_token.used_at is not None

    async def test_invalid_token_returns_400(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/verify-email?token=does-not-exist")
        assert resp.status_code == 400
        assert "invalid" in resp.json()["detail"].lower()

    async def test_used_token_rejected(
        self, client: AsyncClient, test_session
    ):
        user = await _make_user(test_session, email="used@example.com", verified=False)
        token = EmailVerificationToken(
            user_id=user.id,
            token="used-token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used_at=datetime.now(timezone.utc),
        )
        test_session.add(token)
        await test_session.commit()

        resp = await client.get("/api/v1/auth/verify-email?token=used-token")
        assert resp.status_code == 400
        assert "used" in resp.json()["detail"].lower()

    async def test_expired_token_rejected(
        self, client: AsyncClient, test_session
    ):
        user = await _make_user(test_session, email="exp@example.com", verified=False)
        token = EmailVerificationToken(
            user_id=user.id,
            token="expired-token",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        test_session.add(token)
        await test_session.commit()

        resp = await client.get("/api/v1/auth/verify-email?token=expired-token")
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()


class TestResendVerification:
    async def test_unknown_email_returns_generic_200(self, client: AsyncClient):
        send_mock = AsyncMock(return_value=True)
        with patch("src.routes.auth.email_service.send_verification_email", send_mock):
            resp = await client.post(
                "/api/v1/auth/resend-verification",
                json={"email": "ghost@example.com"},
            )
        assert resp.status_code == 200
        send_mock.assert_not_awaited()

    async def test_already_verified_does_not_resend(
        self, client: AsyncClient, test_session
    ):
        await _make_user(test_session, email="done@example.com", verified=True)
        send_mock = AsyncMock(return_value=True)
        with patch("src.routes.auth.email_service.send_verification_email", send_mock):
            resp = await client.post(
                "/api/v1/auth/resend-verification",
                json={"email": "done@example.com"},
            )
        assert resp.status_code == 200
        send_mock.assert_not_awaited()

    async def test_unverified_user_gets_new_email(
        self, client: AsyncClient, test_session
    ):
        await _make_user(test_session, email="need@example.com", verified=False)
        send_mock = AsyncMock(return_value=True)
        with patch("src.routes.auth.email_service.send_verification_email", send_mock):
            resp = await client.post(
                "/api/v1/auth/resend-verification",
                json={"email": "need@example.com"},
            )
        assert resp.status_code == 200
        send_mock.assert_awaited_once()
