import pytest
from httpx import AsyncClient
from src.models.models import User, Quote

class TestQuotesIntegration:
    """Integration tests for quotes endpoints"""

    async def test_create_quote(self, client: AsyncClient, auth_headers: dict, test_user: User):
        """Test creating a new quote"""
        quote_data = {
            "customer_name": "John Doe",
            "customer_email": "john@example.com",
            "customer_phone": "+1234567890",
            "customer_address": "123 Main St, City, State",
            "rooms": [
                {
                    "name": "Living Room",
                    "area": 30.0,
                    "wall_area": 50.0,
                    "ceiling_area": 30.0,
                    "floor_area": 30.0,
                    "paint_type": "Premium",
                    "coating_type": "Latex",
                    "labor_hours": 10
                }
            ],
            "notes": "Customer wants eco-friendly paint"
        }
        
        response = await client.post("/quotes/", json=quote_data, headers=auth_headers)
        assert response.status_code == 201
        
        data = response.json()
        assert data["customer_name"] == quote_data["customer_name"]
        assert data["customer_email"] == quote_data["customer_email"]
        assert data["user_id"] == test_user.id
        assert data["status"] == "draft"
        assert "quote_number" in data
        assert "total_amount" in data
        assert len(data["rooms"]) == 1

    async def test_create_quote_unauthorized(self, client: AsyncClient):
        """Test creating quote without authentication"""
        quote_data = {
            "customer_name": "John Doe",
            "customer_email": "john@example.com",
            "rooms": []
        }
        
        response = await client.post("/quotes/", json=quote_data)
        assert response.status_code == 401

    async def test_get_user_quotes(self, client: AsyncClient, auth_headers: dict, test_quote: Quote):
        """Test getting user's quotes"""
        response = await client.get("/quotes/", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) >= 1
        
        # Find our test quote
        quote_found = False
        for quote in data:
            if quote["id"] == test_quote.id:
                quote_found = True
                assert quote["customer_name"] == test_quote.customer_name
                break
        assert quote_found

    async def test_get_quote_by_id(self, client: AsyncClient, auth_headers: dict, test_quote: Quote):
        """Test getting specific quote by ID"""
        response = await client.get(f"/quotes/{test_quote.id}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == test_quote.id
        assert data["customer_name"] == test_quote.customer_name
        assert data["quote_number"] == test_quote.quote_number

    async def test_get_nonexistent_quote(self, client: AsyncClient, auth_headers: dict):
        """Test getting nonexistent quote"""
        response = await client.get("/quotes/99999", headers=auth_headers)
        assert response.status_code == 404

    async def test_update_quote(self, client: AsyncClient, auth_headers: dict, test_quote: Quote):
        """Test updating a quote"""
        update_data = {
            "customer_name": "Jane Smith Updated",
            "customer_email": "jane.updated@example.com",
            "status": "sent"
        }
        
        response = await client.put(f"/quotes/{test_quote.id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["customer_name"] == update_data["customer_name"]
        assert data["customer_email"] == update_data["customer_email"]
        assert data["status"] == update_data["status"]

    async def test_update_nonexistent_quote(self, client: AsyncClient, auth_headers: dict):
        """Test updating nonexistent quote"""
        update_data = {"customer_name": "Updated Name"}
        
        response = await client.put("/quotes/99999", json=update_data, headers=auth_headers)
        assert response.status_code == 404

    async def test_delete_quote(self, client: AsyncClient, auth_headers: dict, test_user: User):
        """Test deleting a quote"""
        # First create a quote to delete
        quote_data = {
            "customer_name": "To Be Deleted",
            "customer_email": "delete@example.com",
            "rooms": []
        }
        
        create_response = await client.post("/quotes/", json=quote_data, headers=auth_headers)
        assert create_response.status_code == 201
        quote_id = create_response.json()["id"]
        
        # Delete the quote
        response = await client.delete(f"/quotes/{quote_id}", headers=auth_headers)
        assert response.status_code == 204
        
        # Verify it's deleted
        get_response = await client.get(f"/quotes/{quote_id}", headers=auth_headers)
        assert get_response.status_code == 404

    async def test_delete_nonexistent_quote(self, client: AsyncClient, auth_headers: dict):
        """Test deleting nonexistent quote"""
        response = await client.delete("/quotes/99999", headers=auth_headers)
        assert response.status_code == 404

    async def test_quote_pdf_generation(self, client: AsyncClient, auth_headers: dict, test_quote: Quote):
        """Test generating PDF for quote"""
        response = await client.get(f"/quotes/{test_quote.id}/pdf", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

    async def test_quote_export_json(self, client: AsyncClient, auth_headers: dict, test_quote: Quote):
        """Test exporting quote as JSON"""
        response = await client.get(f"/quotes/{test_quote.id}/export?format=json", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    async def test_quote_export_csv(self, client: AsyncClient, auth_headers: dict, test_quote: Quote):
        """Test exporting quote as CSV"""
        response = await client.get(f"/quotes/{test_quote.id}/export?format=csv", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv"

    async def test_quote_status_workflow(self, client: AsyncClient, auth_headers: dict, test_quote: Quote):
        """Test quote status workflow transitions"""
        # Draft -> Sent
        response = await client.put(
            f"/quotes/{test_quote.id}", 
            json={"status": "sent"}, 
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "sent"
        
        # Sent -> Approved
        response = await client.put(
            f"/quotes/{test_quote.id}", 
            json={"status": "approved"}, 
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "approved"

    async def test_quote_search(self, client: AsyncClient, auth_headers: dict, test_quote: Quote):
        """Test searching quotes"""
        # Search by customer name
        response = await client.get(
            f"/quotes/?search={test_quote.customer_name}", 
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) >= 1
        
        # Verify our quote is in results
        quote_found = any(quote["id"] == test_quote.id for quote in data)
        assert quote_found

    async def test_quote_filtering_by_status(self, client: AsyncClient, auth_headers: dict, test_quote: Quote):
        """Test filtering quotes by status"""
        response = await client.get(
            f"/quotes/?status={test_quote.status}", 
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        # All returned quotes should have the requested status
        for quote in data:
            assert quote["status"] == test_quote.status

    async def test_quote_pagination(self, client: AsyncClient, auth_headers: dict):
        """Test quote pagination"""
        response = await client.get("/quotes/?page=1&size=5", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 5

    async def test_quote_access_control(self, client: AsyncClient, test_quote: Quote):
        """Test that users can only access their own quotes"""
        # Create another user
        other_user_data = {
            "email": "other@example.com",
            "username": "otheruser",
            "password": "password123",
            "phone_number": "+1234567891",
            "company_name": "Other Company"
        }
        
        await client.post("/auth/register", json=other_user_data)
        
        # Login as other user
        login_data = {
            "username": "other@example.com",
            "password": "password123"
        }
        
        login_response = await client.post("/auth/login", data=login_data)
        other_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        # Try to access the original user's quote
        response = await client.get(f"/quotes/{test_quote.id}", headers=other_headers)
        assert response.status_code == 404  # Should not find quote from other user