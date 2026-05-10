import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient


class TestAIIntegration:
    """Integration tests for AI endpoints"""

    @pytest.fixture(autouse=True)
    def _patch_agent(self):
        """Patch agent_service.chat to avoid live LLM calls in all tests."""
        mock = AsyncMock(return_value={
            "conversation_id": 1,
            "final_message": "Bitte mehr Details.",
            "pdf_path": None,
            "quote_id": None,
            "quote_number": None,
        })
        with patch("src.services.agent_service.agent_service.chat", mock):
            self._agent_chat_mock = mock
            yield

    # ------------------------------------------------------------------
    # POST /api/v1/ai/analyze-project
    # ------------------------------------------------------------------

    async def test_analyze_project(self, client: AsyncClient, auth_headers: dict):
        """Analyze-project returns 200 with analysis, questions, conversation_history."""
        response = await client.post(
            "/api/v1/ai/analyze-project",
            json={"input": "Wohnzimmer 25 m² streichen"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "analysis" in data
        assert "questions" in data
        assert "conversation_history" in data

    async def test_analyze_project_unauthorized(self, client: AsyncClient):
        """Analyze-project without auth returns 401."""
        response = await client.post(
            "/api/v1/ai/analyze-project",
            json={"input": "Wohnzimmer 25 m² streichen"},
        )
        assert response.status_code == 401

    # ------------------------------------------------------------------
    # POST /api/v1/ai/quote-suggestions
    # ------------------------------------------------------------------

    async def test_quote_suggestions(self, client: AsyncClient, auth_headers: dict):
        """Quote-suggestions returns 200 with the three stub fields."""
        response = await client.post(
            "/api/v1/ai/quote-suggestions",
            json={"rooms": [], "customer_preferences": "anything"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "suggested_materials" in data
        assert "labor_breakdown" in data
        assert "alternative_options" in data

    async def test_quote_suggestions_unauthorized(self, client: AsyncClient):
        """Quote-suggestions without auth returns 401."""
        response = await client.post(
            "/api/v1/ai/quote-suggestions",
            json={"rooms": [], "customer_preferences": "anything"},
        )
        assert response.status_code == 401

    # ------------------------------------------------------------------
    # POST /api/v1/ai/quick-quote
    # ------------------------------------------------------------------

    async def test_quick_quote_success(self, client: AsyncClient, auth_headers: dict):
        """Quick-quote returns 200 with quote_id, total_amount, items in envelope."""
        self._agent_chat_mock.return_value = {
            "conversation_id": 2,
            "final_message": "Angebot erstellt.",
            "pdf_path": None,
            "quote_id": None,
            "quote_number": None,
        }
        response = await client.post(
            "/api/v1/ai/quick-quote",
            json={"service_description": "Wohnzimmer streichen, 25 m²"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "quote_id" in data
        assert "total_amount" in data
        assert "items" in data

    async def test_quick_quote_no_agent_quote(self, client: AsyncClient, auth_headers: dict):
        """When agent produces no quote, quick-quote still returns 200 with non-empty notes."""
        self._agent_chat_mock.return_value = {
            "conversation_id": 2,
            "final_message": "Bitte mehr Details angeben.",
            "pdf_path": None,
            "quote_id": None,
            "quote_number": None,
        }
        response = await client.post(
            "/api/v1/ai/quick-quote",
            json={"service_description": "Streichen bitte"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["notes"]

    # ------------------------------------------------------------------
    # GET /api/v1/ai/ai-status
    # ------------------------------------------------------------------

    async def test_ai_status(self, client: AsyncClient):
        """AI status endpoint returns 200 with ai_enabled, capabilities, status."""
        response = await client.get("/api/v1/ai/ai-status")
        assert response.status_code == 200
        data = response.json()
        assert "ai_enabled" in data
        assert "capabilities" in data
        assert "status" in data
