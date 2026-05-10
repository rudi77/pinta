import pytest
from httpx import AsyncClient
from src.models.models import User

class TestAuthIntegration:
    """Integration tests for authentication endpoints"""

    async def test_user_registration(self, client: AsyncClient):
        """Test user registration endpoint"""
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "newpassword123",
            "phone": "+1234567890",
            "company_name": "New Company"
        }

        response = await client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 201

        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["username"] == user_data["username"]
        assert "id" in data
        assert "password" not in data  # Password should not be returned

    async def test_user_registration_duplicate_email(self, client: AsyncClient, test_user: User):
        """Test registration with duplicate email"""
        user_data = {
            "email": test_user.email,
            "username": "differentusername",
            "password": "password123",
            "phone": "+1234567890",
            "company_name": "Company"
        }

        response = await client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    async def test_user_login_success(self, client: AsyncClient, test_user: User):
        """Test successful user login"""
        login_data = {
            "email": test_user.email,
            "password": "testpassword123"
        }

        response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    async def test_user_login_invalid_credentials(self, client: AsyncClient, test_user: User):
        """Test login with invalid credentials"""
        login_data = {
            "email": test_user.email,
            "password": "wrongpassword"
        }

        response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    async def test_user_login_nonexistent_user(self, client: AsyncClient):
        """Test login with nonexistent user"""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "password123"
        }

        response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 401

    async def test_get_current_user(self, client: AsyncClient, auth_headers: dict, test_user: User):
        """Test getting current user information"""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == test_user.id
        assert data["email"] == test_user.email
        assert data["username"] == test_user.username
        assert "password" not in data

    async def test_get_current_user_without_auth(self, client: AsyncClient):
        """Test getting current user without authentication"""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_refresh_token(self, client: AsyncClient, test_user: User):
        """Test token refresh via Bearer header (endpoint uses HTTPBearer dependency)"""
        login_data = {
            "email": test_user.email,
            "password": "testpassword123"
        }

        login_response = await client.post("/api/v1/auth/login", json=login_data)
        assert login_response.status_code == 200

        tokens = login_response.json()
        refresh_token = tokens["refresh_token"]

        # /auth/refresh reads the token from the Authorization: Bearer header
        response = await client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {refresh_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_token_invalid(self, client: AsyncClient):
        """Test refresh with invalid token (sent as Bearer header)"""
        response = await client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert response.status_code == 401

    async def test_logout(self, client: AsyncClient, auth_headers: dict):
        """Test user logout"""
        response = await client.post("/api/v1/auth/logout", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"

    async def test_logout_without_auth(self, client: AsyncClient):
        """Test logout without authentication"""
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 401

    async def test_password_change(self, client: AsyncClient, auth_headers: dict):
        """Test password change (endpoint reads old_password/new_password as query params)"""
        response = await client.post(
            "/api/v1/auth/change-password",
            params={"old_password": "testpassword123", "new_password": "newtestpassword456"},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "password changed successfully" in response.json()["message"].lower()

    async def test_password_change_wrong_current(self, client: AsyncClient, auth_headers: dict):
        """Test password change with wrong current password"""
        response = await client.post(
            "/api/v1/auth/change-password",
            params={"old_password": "wrongpassword", "new_password": "newtestpassword456"},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "incorrect current password" in response.json()["detail"].lower()
