import pytest
from httpx import AsyncClient
from src.models.models import User

class TestUsersIntegration:
    """Integration tests for user management endpoints"""

    async def test_get_user_profile(self, client: AsyncClient, auth_headers: dict, test_user: User):
        """Test getting user profile"""
        response = await client.get("/api/v1/users/profile", headers=auth_headers)
        assert response.status_code == 200

        profile = response.json()
        assert profile["id"] == test_user.id
        assert profile["email"] == test_user.email
        assert profile["username"] == test_user.username
        assert profile["company_name"] == test_user.company_name
        assert "password" not in profile

    async def test_update_user_profile(self, client: AsyncClient, auth_headers: dict, test_user: User):
        """Test updating user profile"""
        update_data = {
            "username": "updated_username",
            "company_name": "Updated Company Name",
            "phone": "+9876543210",
        }

        response = await client.put("/api/v1/users/profile", json=update_data, headers=auth_headers)
        assert response.status_code == 200

        updated_profile = response.json()
        assert updated_profile["username"] == update_data["username"]
        assert updated_profile["company_name"] == update_data["company_name"]
        assert updated_profile["phone"] == update_data["phone"]

    async def test_update_profile_unauthorized(self, client: AsyncClient):
        """Test updating profile without authentication"""
        update_data = {"username": "unauthorized_update"}

        response = await client.put("/api/v1/users/profile", json=update_data)
        assert response.status_code == 401

    async def test_delete_user_account(self, client: AsyncClient):
        """Test deleting the authenticated user's account via DELETE /api/v1/users/profile"""
        user_data = {
            "email": "todelete@example.com",
            "username": "todelete",
            "password": "deletepassword123",
            "company_name": "Delete Test Company",
        }

        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == 201

        login_data = {"email": "todelete@example.com", "password": "deletepassword123"}
        login_response = await client.post("/api/v1/auth/login", json=login_data)
        assert login_response.status_code == 200
        delete_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = await client.delete("/api/v1/users/profile", headers=delete_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Account deleted successfully"

        # Subsequent requests with the same token should be rejected
        profile_response = await client.get("/api/v1/users/profile", headers=delete_headers)
        assert profile_response.status_code == 401

    async def test_get_user_quota(self, client: AsyncClient, auth_headers: dict):
        """Test getting user quota information"""
        response = await client.get("/api/v1/users/quota", headers=auth_headers)
        assert response.status_code == 200

        quota = response.json()
        assert "is_premium" in quota
        assert "quotes_used" in quota
        assert "quotes_remaining" in quota
        assert "total_available" in quota
        assert "additional_quotes" in quota

    async def test_get_user_quota_unauthorized(self, client: AsyncClient):
        """Test getting quota without authentication"""
        response = await client.get("/api/v1/users/quota")
        assert response.status_code == 401
