"""Tests for the agent-pdf-info quote endpoint (P0.3).

These cover the path that the frontend now uses to resolve a Quote → its
agent-generated PDF in `.taskforce_maler/quotes/`. The endpoint is the
seam between the legacy quote DB record and the new agent PDF pipeline.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.models.models import Quote, User
from src.routes import quotes as quotes_module


@pytest.fixture
def patch_agent_quotes_dir(monkeypatch, tmp_path):
    """Redirect _AGENT_QUOTES_DIR to a tmp_path so tests don't touch real files."""
    monkeypatch.setattr(quotes_module, "_AGENT_QUOTES_DIR", tmp_path)
    return tmp_path


@pytest.mark.asyncio
async def test_agent_pdf_info_returns_url_when_file_exists(
    client: AsyncClient,
    auth_headers: dict,
    test_quote: Quote,
    patch_agent_quotes_dir,
):
    pdf_path = patch_agent_quotes_dir / f"20260504_{test_quote.quote_number}_test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy")

    response = await client.get(
        f"/api/v1/quotes/{test_quote.id}/agent-pdf-info",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pdf_filename"] == pdf_path.name
    assert body["pdf_url"] == f"/api/v1/agent/pdf/{pdf_path.name}"


@pytest.mark.asyncio
async def test_agent_pdf_info_returns_404_when_pdf_missing(
    client: AsyncClient,
    auth_headers: dict,
    test_quote: Quote,
    patch_agent_quotes_dir,
):
    response = await client.get(
        f"/api/v1/quotes/{test_quote.id}/agent-pdf-info",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "PDF nicht gefunden" in response.json()["detail"]


@pytest.mark.asyncio
async def test_agent_pdf_info_returns_404_for_unknown_quote(
    client: AsyncClient,
    auth_headers: dict,
    patch_agent_quotes_dir,
):
    response = await client.get(
        "/api/v1/quotes/999999/agent-pdf-info",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "Kostenvoranschlag nicht gefunden" in response.json()["detail"]


@pytest.mark.asyncio
async def test_agent_pdf_info_returns_newest_match_when_multiple(
    client: AsyncClient,
    auth_headers: dict,
    test_quote: Quote,
    patch_agent_quotes_dir,
):
    older = patch_agent_quotes_dir / f"old_{test_quote.quote_number}.pdf"
    older.write_bytes(b"%PDF-1.4 old")
    newer = patch_agent_quotes_dir / f"new_{test_quote.quote_number}.pdf"
    newer.write_bytes(b"%PDF-1.4 new")

    import os
    import time
    now = time.time()
    os.utime(older, (now - 100, now - 100))
    os.utime(newer, (now, now))

    response = await client.get(
        f"/api/v1/quotes/{test_quote.id}/agent-pdf-info",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["pdf_filename"] == newer.name


@pytest.mark.asyncio
async def test_agent_pdf_info_requires_auth(
    client: AsyncClient,
    test_quote: Quote,
):
    response = await client.get(
        f"/api/v1/quotes/{test_quote.id}/agent-pdf-info",
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_agent_pdf_info_does_not_leak_other_users_quotes(
    client: AsyncClient,
    test_session,
    auth_headers: dict,
    patch_agent_quotes_dir,
):
    """A user must not be able to resolve another user's quote PDF."""
    from src.core.security import get_password_hash
    import uuid

    other_user = User(
        email=f"other-{uuid.uuid4().hex[:6]}@example.com",
        username=f"other-{uuid.uuid4().hex[:6]}",
        hashed_password=get_password_hash("xx"),
        is_active=True,
        is_verified=True,
    )
    test_session.add(other_user)
    await test_session.commit()
    await test_session.refresh(other_user)

    other_quote = Quote(
        quote_number="OTHER-001",
        customer_name="x",
        user_id=other_user.id,
        project_title="Andere Wohnung",
        total_amount=0,
    )
    test_session.add(other_quote)
    await test_session.commit()
    await test_session.refresh(other_quote)

    pdf_path = patch_agent_quotes_dir / f"{other_quote.quote_number}.pdf"
    pdf_path.write_bytes(b"%PDF")

    response = await client.get(
        f"/api/v1/quotes/{other_quote.id}/agent-pdf-info",
        headers=auth_headers,
    )

    assert response.status_code == 404
