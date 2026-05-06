"""Integration-Tests für `/api/v1/agent/*`-Endpoints.

Adressiert TODOList.md ⬜ Tech-Schuld: "Integration-Tests für `/api/v1/agent/*`
mit gemocktem AgentService (Plan vorgesehen, noch nicht geschrieben)".

Strategie:
- Auth-Pfade prüfen wir ohne agent_service-Mock — Auth-Failures kommen vor
  dem Service-Aufruf zurück.
- Behavior-Tests mocken `src.routes.agent.agent_service` via monkeypatch
  direkt im Test, damit kein Konftest-Edit nötig ist und keine echte LLM/DB
  gerufen wird.
- Bot-Endpoints brauchen `X-Bot-Service-Token`, das wir in
  `settings.bot_service_token` setzen.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.models.models import User


# ── User-Endpoints: Auth-Gates ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_chat_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/agent/chat",
        json={"message": "Hello", "channel": "web"},
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_reset_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/v1/agent/reset")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_conversations_list_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/agent/conversations")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_linking_token_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/v1/agent/linking-token")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_channel_links_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/agent/channel-links")
    assert response.status_code in (401, 403)


# ── User-Endpoints: Behavior with mocked agent_service ─────────────────


class _FakeAgentService:
    """In-Memory-Stub von AgentService — keine DB-, keine LLM-Calls."""

    def __init__(self) -> None:
        self.chat_calls: list[tuple] = []
        self.reset_calls: list[tuple] = []

    async def chat(self, db, user, message, *, channel="web", attachments_block=None):
        self.chat_calls.append((user.id, message, channel))
        return {
            "conversation_id": 12345,
            "final_message": f"Echo: {message}",
            "status": "completed",
            "pdf_path": None,
            "quote_id": None,
            "quote_number": None,
        }

    async def reset(self, db, user, *, channel="web"):
        self.reset_calls.append((user.id, channel))
        from src.models.models import Conversation

        return Conversation(id=99999, user_id=user.id, channel=channel)


@pytest.mark.asyncio
async def test_chat_returns_expected_response_shape(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeAgentService()
    monkeypatch.setattr("src.routes.agent.agent_service", fake)

    response = await client.post(
        "/api/v1/agent/chat",
        headers=auth_headers,
        json={"message": "Hallo Manfred", "channel": "web"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["conversation_id"] == 12345
    assert "Echo: Hallo Manfred" in body["final_message"]
    assert body["status"] == "completed"
    assert len(fake.chat_calls) == 1


@pytest.mark.asyncio
async def test_reset_returns_new_conversation_id(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeAgentService()
    monkeypatch.setattr("src.routes.agent.agent_service", fake)

    response = await client.post(
        "/api/v1/agent/reset",
        headers=auth_headers,
        params={"channel": "web"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["new_conversation_id"] == 99999
    assert body["channel"] == "web"


@pytest.mark.asyncio
async def test_chat_rejects_empty_message(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pydantic-Validation: AgentChatRequest.message ist min_length=1."""
    fake = _FakeAgentService()
    monkeypatch.setattr("src.routes.agent.agent_service", fake)

    response = await client.post(
        "/api/v1/agent/chat",
        headers=auth_headers,
        json={"message": "", "channel": "web"},
    )
    assert response.status_code == 422, response.text


# ── Bot-Endpoints: Service-Token-Auth ──────────────────────────────────


@pytest.mark.asyncio
async def test_bot_chat_rejects_without_service_token(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/agent/bot/chat",
        json={"message": "Hi"},
        headers={"X-Channel": "telegram", "X-External-Id": "12345"},
    )
    # 422 (header missing) or 401 (bot guard) sind beide akzeptabel — wichtig
    # ist, dass der Endpoint NICHT 200 zurückgibt.
    assert response.status_code in (401, 422)


@pytest.mark.asyncio
async def test_bot_chat_rejects_invalid_service_token(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.routes.agent.settings.bot_service_token",
        "real-secret-token",
        raising=False,
    )
    response = await client.post(
        "/api/v1/agent/bot/chat",
        json={"message": "Hi"},
        headers={
            "X-Bot-Service-Token": "wrong-token",
            "X-Channel": "telegram",
            "X-External-Id": "12345",
        },
    )
    assert response.status_code == 401, response.text


# ── PDF-Download: Path-traversal-Defence ────────────────────────────────


@pytest.mark.asyncio
async def test_pdf_download_rejects_path_traversal(
    client: AsyncClient,
    auth_headers: dict,
) -> None:
    response = await client.get(
        "/api/v1/agent/pdf/..%2F..%2Fetc%2Fpasswd",
        headers=auth_headers,
    )
    # Entweder 400 (path traversal explicit detected), 404 (slug nicht
    # gefunden weil ".." Teil des Namens war), 403 oder 401.
    # 200 wäre der Bug.
    assert response.status_code != 200, (
        f"PDF endpoint allowed traversal! status={response.status_code}"
    )


@pytest.mark.asyncio
async def test_pdf_download_unknown_slug_returns_404(
    client: AsyncClient,
    auth_headers: dict,
) -> None:
    response = await client.get(
        "/api/v1/agent/pdf/nonexistent-quote-12345.pdf",
        headers=auth_headers,
    )
    assert response.status_code == 404


# ── Linking-Token mit gemocktem `issue_linking_token` ──────────────────


@pytest.mark.asyncio
async def test_linking_token_returns_token_and_deep_link(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import datetime, timedelta, timezone

    expires = datetime.now(timezone.utc) + timedelta(days=30)

    async def _fake_issue(db, user, *, channel="telegram"):
        return "TESTTOKEN1234", expires

    monkeypatch.setattr(
        "src.routes.agent.issue_linking_token",
        _fake_issue,
    )
    monkeypatch.setattr(
        "src.routes.agent.settings.telegram_bot_username",
        "BluLieferantenBot",
        raising=False,
    )

    response = await client.post(
        "/api/v1/agent/linking-token",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token"] == "TESTTOKEN1234"
    assert body["channel"] == "telegram"
    assert body["bot_username"] == "BluLieferantenBot"
    assert body["deep_link"] == "https://t.me/BluLieferantenBot?start=TESTTOKEN1234"
    assert body["command"] == "/link TESTTOKEN1234"
