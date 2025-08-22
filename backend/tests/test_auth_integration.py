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
            "phone_number": "+1234567890",
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
            "phone_number": "+1234567890",
            "company_name": "Company"
        }
        
        response = await client.post("/api/v1/auth/register", json=user_data)
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

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
        
        response = await client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 401
        assert "invalid credentials" in response.json()["detail"].lower()

    async def test_user_login_nonexistent_user(self, client: AsyncClient):
        """Test login with nonexistent user"""
        login_data = {
            "username": "nonexistent@example.com",
            "password": "password123"
        }
        
        response = await client.post("/api/v1/auth/login", data=login_data)
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
        """Test token refresh"""
        # First login to get tokens
        login_data = {
            "username": test_user.email,
            "password": "testpassword123"
        }
        
        login_response = await client.post("/api/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        tokens = login_response.json()
        refresh_token = tokens["refresh_token"]
        
        # Use refresh token to get new access token
        refresh_data = {"refresh_token": refresh_token}
        response = await client.post("/api/v1/auth/refresh", json=refresh_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_token_invalid(self, client: AsyncClient):
        """Test refresh with invalid token"""
        refresh_data = {"refresh_token": "invalid.token.here"}
        response = await client.post("/api/v1/auth/refresh", json=refresh_data)
        assert response.status_code == 401

    async def test_logout(self, client: AsyncClient, auth_headers: dict):
        """Test user logout"""
        response = await client.post("/api/v1/auth/logout", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"

    async def test_logout_without_auth(self, client: AsyncClient):
        """Test logout without authentication"""
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 401

    async def test_password_change(self, client: AsyncClient, auth_headers: dict):
        """Test password change"""
        password_data = {
            "current_password": "testpassword123",
            "new_password": "newtestpassword456"
        }
        
        response = await client.post("/api/v1/auth/change-password", json=password_data, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Password updated successfully"

    async def test_password_change_wrong_current(self, client: AsyncClient, auth_headers: dict):
        """Test password change with wrong current password"""
        password_data = {
            "current_password": "wrongpassword",
            "new_password": "newtestpassword456"
        }
        
        response = await client.post("/api/v1/auth/change-password", json=password_data, headers=auth_headers)
        assert response.status_code == 400
        assert "current password is incorrect" in response.json()["detail"].lower()

    async def test_protected_endpoint_with_blacklisted_token(self, client: AsyncClient, test_user: User):
        """Test that blacklisted tokens cannot access protected endpoints"""
        # Login to get token
        login_data = {
            "username": test_user.email,
            "password": "testpassword123"
        }
        
        login_response = await client.post("/api/v1/auth/login", data=login_data)
        tokens = login_response.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        
        # Logout to blacklist the token
        await client.post("/api/v1/auth/logout", headers=headers)
        
        # Try to use the blacklisted token
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401