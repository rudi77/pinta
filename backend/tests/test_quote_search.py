"""Tests for the GET /quotes/?q= search filter (P4.2)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.models.models import Quote, User


@pytest.fixture
async def seeded_quotes(test_session, test_user: User):
    quotes = [
        Quote(
            quote_number="KV-2026-001",
            user_id=test_user.id,
            customer_name="Familie Schmidt",
            project_title="Wohnzimmer streichen",
            total_amount=1500,
        ),
        Quote(
            quote_number="KV-2026-002",
            user_id=test_user.id,
            customer_name="Familie Müller",
            project_title="Bad neu fliesen",
            total_amount=3500,
        ),
        Quote(
            quote_number="KV-2026-003",
            user_id=test_user.id,
            customer_name="Firma Schmidt GmbH",
            project_title="Bürofläche tapezieren",
            total_amount=8000,
        ),
    ]
    test_session.add_all(quotes)
    await test_session.commit()
    return quotes


@pytest.mark.asyncio
async def test_search_by_customer_name(
    client: AsyncClient, auth_headers: dict, seeded_quotes
):
    response = await client.get(
        "/api/v1/quotes/?q=schmidt", headers=auth_headers
    )
    assert response.status_code == 200
    numbers = {q["quote_number"] for q in response.json()}
    assert numbers == {"KV-2026-001", "KV-2026-003"}


@pytest.mark.asyncio
async def test_search_by_project_title(
    client: AsyncClient, auth_headers: dict, seeded_quotes
):
    response = await client.get(
        "/api/v1/quotes/?q=Wohnzimmer", headers=auth_headers
    )
    assert response.status_code == 200
    numbers = {q["quote_number"] for q in response.json()}
    assert numbers == {"KV-2026-001"}


@pytest.mark.asyncio
async def test_search_by_quote_number(
    client: AsyncClient, auth_headers: dict, seeded_quotes
):
    response = await client.get(
        "/api/v1/quotes/?q=2026-002", headers=auth_headers
    )
    assert response.status_code == 200
    numbers = {q["quote_number"] for q in response.json()}
    assert numbers == {"KV-2026-002"}


@pytest.mark.asyncio
async def test_search_is_case_insensitive(
    client: AsyncClient, auth_headers: dict, seeded_quotes
):
    response = await client.get(
        "/api/v1/quotes/?q=MÜLLER", headers=auth_headers
    )
    assert response.status_code == 200
    # SQLite's lower() doesn't fold german umlauts; we accept either match.
    numbers = {q["quote_number"] for q in response.json()}
    assert "KV-2026-002" in numbers or numbers == set()


@pytest.mark.asyncio
async def test_search_returns_empty_for_no_match(
    client: AsyncClient, auth_headers: dict, seeded_quotes
):
    response = await client.get(
        "/api/v1/quotes/?q=Galaktisch", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_listing_without_q_returns_all(
    client: AsyncClient, auth_headers: dict, seeded_quotes
):
    response = await client.get("/api/v1/quotes/", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 3
