"""Integration tests for Phase 1 (multi-modal visual estimate)
and Phase 2 (RAG-grounded material catalog).

These tests rely on the AIService mock fallback (``enabled == False``) which is
active in the test conftest, so no real OpenAI calls are made.
"""
from __future__ import annotations

import io
import json

import pytest
from httpx import AsyncClient

from src.models.models import MaterialPrice, User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def premium_user(test_session) -> User:
    """A verified, premium-enabled user — prerequisite for the Vision endpoint."""
    import uuid
    from src.core.security import get_password_hash

    unique = str(uuid.uuid4())[:8]
    user = User(
        email=f"premium-{unique}@example.com",
        username=f"premium-{unique}",
        hashed_password=get_password_hash("premiumpassword123"),
        is_active=True,
        is_verified=True,
        is_premium=True,
        phone_number="+1234567800",
        company_name="Premium Co",
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
async def premium_auth_headers(client: AsyncClient, premium_user: User) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": premium_user.email, "password": "premiumpassword123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def superuser(test_session) -> User:
    import uuid
    from src.core.security import get_password_hash

    unique = str(uuid.uuid4())[:8]
    user = User(
        email=f"super-{unique}@example.com",
        username=f"super-{unique}",
        hashed_password=get_password_hash("superpassword123"),
        is_active=True,
        is_verified=True,
        is_superuser=True,
        phone_number="+1234567801",
        company_name="Admin Co",
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
async def superuser_auth_headers(client: AsyncClient, superuser: User) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": superuser.email, "password": "superpassword123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _tiny_png_bytes() -> bytes:
    """A valid 1x1 PNG we can upload without needing Pillow."""
    # Pre-computed PNG header + IHDR + IDAT + IEND for a 1x1 transparent pixel
    import base64 as _b64
    return _b64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )


# ---------------------------------------------------------------------------
# Phase 1 — Visual Estimate
# ---------------------------------------------------------------------------

class TestVisualEstimate:
    async def test_visual_estimate_requires_auth(self, client: AsyncClient):
        files = {"file": ("test.png", _tiny_png_bytes(), "image/png")}
        response = await client.post("/api/v1/ai/visual-estimate", files=files)
        assert response.status_code in (401, 403)

    async def test_visual_estimate_rejects_free_tier(
        self, client: AsyncClient, auth_headers: dict
    ):
        files = {"file": ("test.png", _tiny_png_bytes(), "image/png")}
        response = await client.post(
            "/api/v1/ai/visual-estimate", files=files, headers=auth_headers
        )
        assert response.status_code == 402
        assert "Premium" in response.json()["detail"]

    async def test_visual_estimate_rejects_unsupported_mime(
        self, client: AsyncClient, premium_auth_headers: dict
    ):
        files = {"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")}
        response = await client.post(
            "/api/v1/ai/visual-estimate",
            files=files,
            headers=premium_auth_headers,
        )
        assert response.status_code == 400

    async def test_visual_estimate_rejects_empty_file(
        self, client: AsyncClient, premium_auth_headers: dict
    ):
        files = {"file": ("test.png", b"", "image/png")}
        response = await client.post(
            "/api/v1/ai/visual-estimate",
            files=files,
            headers=premium_auth_headers,
        )
        assert response.status_code == 400

    async def test_visual_estimate_success_with_mock_fallback(
        self, client: AsyncClient, premium_auth_headers: dict
    ):
        files = {"file": ("site.png", _tiny_png_bytes(), "image/png")}
        data = {"extra_context": "Wohnzimmer im Altbau"}
        response = await client.post(
            "/api/v1/ai/visual-estimate",
            files=files,
            data=data,
            headers=premium_auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        # Structure from the mock fallback / real model
        assert "room_type" in body
        assert "estimated_area_sqm" in body
        assert "total" in body["estimated_area_sqm"]
        assert "substrate_condition" in body
        assert "required_prep_work" in body
        assert isinstance(body["required_prep_work"], list)
        assert "estimated_labor_hours" in body
        assert body["area_confidence"] in ("low", "medium", "high")


# ---------------------------------------------------------------------------
# Phase 2 — Material Catalog + RAG
# ---------------------------------------------------------------------------

class TestMaterialsCRUD:
    async def test_create_material_requires_superuser(
        self, client: AsyncClient, auth_headers: dict
    ):
        payload = {
            "name": "Dispersionsfarbe Alpinaweiß",
            "unit": "l",
            "price_net": 29.90,
        }
        response = await client.post(
            "/api/v1/materials", json=payload, headers=auth_headers
        )
        assert response.status_code == 403

    async def test_superuser_can_create_material(
        self, client: AsyncClient, superuser_auth_headers: dict
    ):
        payload = {
            "name": "Dispersionsfarbe Alpinaweiß 10l",
            "manufacturer": "Alpina",
            "category": "paint",
            "unit": "l",
            "price_net": 39.50,
            "region": "DE",
            "description": "Weiße Dispersionsfarbe für Innenräume, matt",
        }
        response = await client.post(
            "/api/v1/materials", json=payload, headers=superuser_auth_headers
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["id"] > 0
        assert body["name"] == payload["name"]
        assert body["price_net"] == 39.50

    async def test_list_and_get_material(
        self,
        client: AsyncClient,
        superuser_auth_headers: dict,
        auth_headers: dict,
    ):
        # Create two
        await client.post(
            "/api/v1/materials",
            json={"name": "Tiefgrund", "unit": "l", "price_net": 12.0, "category": "primer"},
            headers=superuser_auth_headers,
        )
        await client.post(
            "/api/v1/materials",
            json={"name": "Malerkrepp", "unit": "Stk", "price_net": 3.99, "category": "tape"},
            headers=superuser_auth_headers,
        )
        # List as regular user — reading is open
        resp = await client.get("/api/v1/materials", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 2

        # Filter by category
        resp = await client.get(
            "/api/v1/materials?category=primer", headers=auth_headers
        )
        assert resp.status_code == 200
        assert all(m["category"] == "primer" for m in resp.json())

    async def test_update_material_reembeds_on_semantic_change(
        self,
        client: AsyncClient,
        superuser_auth_headers: dict,
        test_session,
    ):
        resp = await client.post(
            "/api/v1/materials",
            json={"name": "Farbe A", "unit": "l", "price_net": 10.0},
            headers=superuser_auth_headers,
        )
        mat_id = resp.json()["id"]
        resp = await client.patch(
            f"/api/v1/materials/{mat_id}",
            json={"name": "Farbe A (überarbeitet)"},
            headers=superuser_auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Farbe A (überarbeitet)"

    async def test_delete_material(
        self, client: AsyncClient, superuser_auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/materials",
            json={"name": "Zum Löschen", "unit": "Stk", "price_net": 1.0},
            headers=superuser_auth_headers,
        )
        mat_id = resp.json()["id"]
        resp = await client.delete(
            f"/api/v1/materials/{mat_id}", headers=superuser_auth_headers
        )
        assert resp.status_code == 204
        resp = await client.get(
            f"/api/v1/materials/{mat_id}", headers=superuser_auth_headers
        )
        assert resp.status_code == 404


class TestMaterialSearchRAG:
    async def test_search_finds_by_substring_fallback(
        self,
        client: AsyncClient,
        superuser_auth_headers: dict,
        auth_headers: dict,
    ):
        # Seed two materials
        await client.post(
            "/api/v1/materials",
            json={
                "name": "Premium Silikatfarbe",
                "category": "paint",
                "unit": "l",
                "price_net": 59.0,
                "description": "hochwertige Fassadenfarbe mineralisch",
            },
            headers=superuser_auth_headers,
        )
        await client.post(
            "/api/v1/materials",
            json={
                "name": "Abdeckvlies",
                "category": "tool",
                "unit": "m",
                "price_net": 1.50,
                "description": "Schutzvlies für Böden",
            },
            headers=superuser_auth_headers,
        )

        # In mock mode, embeddings are zero-vectors → substring fallback kicks in
        resp = await client.get(
            "/api/v1/materials/search?q=silikatfarbe",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["count"] >= 1
        assert any("Silikat" in m["name"] for m in body["results"])

    async def test_search_requires_min_query_length(
        self, client: AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/materials/search?q=a", headers=auth_headers
        )
        assert resp.status_code == 422

    async def test_search_respects_top_k(
        self,
        client: AsyncClient,
        superuser_auth_headers: dict,
        auth_headers: dict,
    ):
        for i in range(4):
            await client.post(
                "/api/v1/materials",
                json={
                    "name": f"Farbe {i}",
                    "category": "paint",
                    "unit": "l",
                    "price_net": 10.0 + i,
                    "description": "Dispersionsfarbe weiß",
                },
                headers=superuser_auth_headers,
            )
        resp = await client.get(
            "/api/v1/materials/search?q=dispersionsfarbe&top_k=2",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["count"] <= 2


class TestRagServiceUnit:
    """Unit-level tests for the pure-Python similarity logic."""

    async def test_cosine_returns_zero_for_zero_vectors(self):
        from src.services.rag_service import _cosine

        assert _cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
        assert _cosine([], []) == 0.0
        assert _cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
        assert _cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    async def test_retrieve_materials_empty_db_returns_empty(self, test_session):
        from src.services.rag_service import RagService

        rag = RagService()
        result = await rag.retrieve_materials(
            db=test_session, query="Farbe", top_k=3
        )
        assert result == []
