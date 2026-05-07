import pytest
from httpx import AsyncClient
from src.models.models import User, Quote

# Minimal valid payload satisfying QuoteCreate (QuoteBase + items list).
_VALID_QUOTE_PAYLOAD = {
    "customer_name": "Max Mustermann",
    "customer_email": "max@example.com",
    "customer_phone": "+4312345678",
    "customer_address": "Musterstraße 1, Wien",
    "project_title": "Wohnzimmer streichen",
    "project_description": "Wände und Decke streichen, weiß, Latex",
    "total_amount": 500.0,
    "items": [
        {
            "description": "Wandfarbe auftragen",
            "quantity": 30.0,
            "unit_price": 15.0,
            "total_price": 450.0,
        }
    ],
}


class TestQuotesIntegration:
    """Integration tests for quotes endpoints"""

    async def test_create_quote(self, client: AsyncClient, auth_headers: dict, test_user: User):
        """Test creating a new quote"""
        response = await client.post("/api/v1/quotes/", json=_VALID_QUOTE_PAYLOAD, headers=auth_headers)
        assert response.status_code in (200, 201)

        data = response.json()
        assert data["customer_name"] == _VALID_QUOTE_PAYLOAD["customer_name"]
        assert data["customer_email"] == _VALID_QUOTE_PAYLOAD["customer_email"]
        assert data["user_id"] == test_user.id
        assert data["status"] == "draft"
        assert "quote_number" in data
        assert "total_amount" in data
        assert isinstance(data["items"], list)

    async def test_create_quote_unauthorized(self, client: AsyncClient):
        """Test creating quote without authentication"""
        response = await client.post("/api/v1/quotes/", json=_VALID_QUOTE_PAYLOAD)
        assert response.status_code == 401

    async def test_get_user_quotes(self, client: AsyncClient, auth_headers: dict, test_quote: Quote):
        """Test getting user's quotes"""
        response = await client.get("/api/v1/quotes/", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 1
        assert any(q["id"] == test_quote.id for q in data)

    async def test_get_quote_by_id(self, client: AsyncClient, auth_headers: dict, test_quote: Quote):
        """Test getting specific quote by ID"""
        response = await client.get(f"/api/v1/quotes/{test_quote.id}", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == test_quote.id
        assert data["customer_name"] == test_quote.customer_name
        assert data["quote_number"] == test_quote.quote_number

    async def test_get_nonexistent_quote(self, client: AsyncClient, auth_headers: dict):
        """Test getting nonexistent quote"""
        response = await client.get("/api/v1/quotes/99999", headers=auth_headers)
        assert response.status_code == 404

    async def test_update_quote(self, client: AsyncClient, auth_headers: dict, test_quote: Quote):
        """Test updating a quote — PUT requires all QuoteBase fields"""
        update_data = {
            "customer_name": "Jane Smith Updated",
            "customer_email": "jane.updated@example.com",
            "project_title": test_quote.project_title,
            "project_description": test_quote.project_description,
            "total_amount": test_quote.total_amount,
            "status": "sent",
        }

        response = await client.put(
            f"/api/v1/quotes/{test_quote.id}", json=update_data, headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["customer_name"] == update_data["customer_name"]
        assert data["customer_email"] == update_data["customer_email"]
        assert data["status"] == update_data["status"]

    async def test_update_nonexistent_quote(self, client: AsyncClient, auth_headers: dict):
        """Test updating nonexistent quote"""
        update_data = {
            "customer_name": "Updated Name",
            "project_title": "Some Title",
            "project_description": "Some description",
            "total_amount": 100.0,
        }

        response = await client.put("/api/v1/quotes/99999", json=update_data, headers=auth_headers)
        assert response.status_code == 404

    async def test_delete_quote(self, client: AsyncClient, auth_headers: dict, test_user: User):
        """Test deleting a quote"""
        create_response = await client.post(
            "/api/v1/quotes/", json=_VALID_QUOTE_PAYLOAD, headers=auth_headers
        )
        assert create_response.status_code in (200, 201)
        quote_id = create_response.json()["id"]

        # Route returns SuccessResponse (200), not 204
        response = await client.delete(f"/api/v1/quotes/{quote_id}", headers=auth_headers)
        assert response.status_code == 200

        get_response = await client.get(f"/api/v1/quotes/{quote_id}", headers=auth_headers)
        assert get_response.status_code == 404

    async def test_delete_nonexistent_quote(self, client: AsyncClient, auth_headers: dict):
        """Test deleting nonexistent quote"""
        response = await client.delete("/api/v1/quotes/99999", headers=auth_headers)
        assert response.status_code == 404

    # test_quote_pdf_generation removed: GET /quotes/{id}/pdf does not exist.
    # Use GET /quotes/{id}/agent-pdf-info → GET /agent/pdf/{name} instead.

    # test_quote_export_json removed: export is POST /quotes/{id}/export with ExportOptions body,
    # not a GET with ?format= query param.

    # test_quote_export_csv removed: same reason as test_quote_export_json.

    async def test_quote_status_workflow(
        self, client: AsyncClient, auth_headers: dict, test_quote: Quote
    ):
        """Test quote status workflow transitions"""
        base = {
            "customer_name": test_quote.customer_name,
            "project_title": test_quote.project_title,
            "project_description": test_quote.project_description,
            "total_amount": test_quote.total_amount,
        }

        # Draft -> Sent
        response = await client.put(
            f"/api/v1/quotes/{test_quote.id}",
            json={**base, "status": "sent"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "sent"

        # Sent -> Approved
        response = await client.put(
            f"/api/v1/quotes/{test_quote.id}",
            json={**base, "status": "approved"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "approved"

    async def test_quote_search(self, client: AsyncClient, auth_headers: dict, test_quote: Quote):
        """Test searching quotes — uses ?q= parameter, not ?search="""
        response = await client.get(
            f"/api/v1/quotes/?q={test_quote.customer_name}",
            headers=auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 1
        assert any(q["id"] == test_quote.id for q in data)

    async def test_quote_filtering_by_status(
        self, client: AsyncClient, auth_headers: dict, test_quote: Quote
    ):
        """Test filtering quotes by status — uses ?status_filter= parameter, not ?status="""
        response = await client.get(
            f"/api/v1/quotes/?status_filter={test_quote.status}",
            headers=auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        for quote in data:
            assert quote["status"] == test_quote.status

    async def test_quote_pagination(self, client: AsyncClient, auth_headers: dict):
        """Test quote pagination — uses ?limit= and ?offset=, not ?page= and ?size="""
        response = await client.get("/api/v1/quotes/?limit=5&offset=0", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 5

    async def test_quote_access_control(self, client: AsyncClient, test_quote: Quote):
        """Test that users can only access their own quotes"""
        other_user_data = {
            "email": "other@example.com",
            "username": "otheruser",
            "password": "password123",
            "company_name": "Other Company",
        }

        register_response = await client.post("/api/v1/auth/register", json=other_user_data)
        assert register_response.status_code in (200, 201)

        # Auth uses JSON body with email=, not OAuth2 form with username=
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "other@example.com", "password": "password123"},
        )
        assert login_response.status_code == 200
        other_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = await client.get(f"/api/v1/quotes/{test_quote.id}", headers=other_headers)
        assert response.status_code == 404

    async def test_free_tier_quota_blocks_fourth_quote(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Free users get 3 quotes/month; the 4th must be refused with 403."""
        payload = {
            "customer_name": "Quota Test",
            "project_title": "Quota Test Project",
            "project_description": "Verifying free-tier enforcement",
            "total_amount": 100.0,
            "items": [
                {
                    "description": "Test item",
                    "quantity": 1,
                    "unit_price": 100.0,
                    "total_price": 100.0,
                }
            ],
        }

        for _ in range(3):
            ok = await client.post("/api/v1/quotes/", json=payload, headers=auth_headers)
            assert ok.status_code in (200, 201), ok.text

        blocked = await client.post("/api/v1/quotes/", json=payload, headers=auth_headers)
        assert blocked.status_code == 403
        assert "limit reached" in blocked.json()["detail"].lower()
