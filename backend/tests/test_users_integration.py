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
            "phone_number": "+9876543210"
        }
        
        response = await client.put("/api/v1/users/profile", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        
        updated_profile = response.json()
        assert updated_profile["username"] == update_data["username"]
        assert updated_profile["company_name"] == update_data["company_name"]
        assert updated_profile["phone_number"] == update_data["phone_number"]

    async def test_update_profile_unauthorized(self, client: AsyncClient):
        """Test updating profile without authentication"""
        update_data = {"username": "unauthorized_update"}
        
        response = await client.put("/api/v1/users/profile", json=update_data)
        assert response.status_code == 401

    async def test_get_user_statistics(self, client: AsyncClient, auth_headers: dict, test_quote):
        """Test getting user statistics"""
        response = await client.get("/api/v1/users/statistics", headers=auth_headers)
        assert response.status_code == 200
        
        stats = response.json()
        assert "total_quotes" in stats
        assert "total_revenue" in stats
        assert "quotes_by_status" in stats
        assert "monthly_activity" in stats
        assert stats["total_quotes"] >= 1  # We have at least one test quote

    async def test_get_user_activity_log(self, client: AsyncClient, auth_headers: dict):
        """Test getting user activity log"""
        response = await client.get("/api/v1/users/activity", headers=auth_headers)
        assert response.status_code == 200
        
        activities = response.json()
        assert isinstance(activities, list)
        # Activities should be ordered by timestamp (most recent first)
        if len(activities) > 1:
            for i in range(len(activities) - 1):
                assert activities[i]["timestamp"] >= activities[i + 1]["timestamp"]

    async def test_get_user_settings(self, client: AsyncClient, auth_headers: dict):
        """Test getting user settings"""
        response = await client.get("/api/v1/users/settings", headers=auth_headers)
        assert response.status_code == 200
        
        settings = response.json()
        assert "notifications" in settings
        assert "theme" in settings
        assert "language" in settings
        assert "timezone" in settings

    async def test_update_user_settings(self, client: AsyncClient, auth_headers: dict):
        """Test updating user settings"""
        settings_data = {
            "notifications": {
                "email_quotes": True,
                "email_reminders": False,
                "sms_notifications": True
            },
            "theme": "dark",
            "language": "de",
            "timezone": "Europe/Berlin"
        }
        
        response = await client.put("/api/v1/users/settings", json=settings_data, headers=auth_headers)
        assert response.status_code == 200
        
        updated_settings = response.json()
        assert updated_settings["theme"] == "dark"
        assert updated_settings["language"] == "de"
        assert updated_settings["timezone"] == "Europe/Berlin"
        assert updated_settings["notifications"]["email_quotes"] is True

    async def test_deactivate_user_account(self, client: AsyncClient, auth_headers: dict):
        """Test deactivating user account"""
        deactivate_data = {
            "password": "testpassword123",
            "reason": "Testing account deactivation"
        }
        
        response = await client.post("/api/v1/users/deactivate", json=deactivate_data, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Account deactivated successfully"

    async def test_deactivate_account_wrong_password(self, client: AsyncClient, auth_headers: dict):
        """Test deactivating account with wrong password"""
        deactivate_data = {
            "password": "wrongpassword",
            "reason": "Testing with wrong password"
        }
        
        response = await client.post("/api/v1/users/deactivate", json=deactivate_data, headers=auth_headers)
        assert response.status_code == 400
        assert "password is incorrect" in response.json()["detail"].lower()

    async def test_export_user_data(self, client: AsyncClient, auth_headers: dict):
        """Test exporting user data (GDPR compliance)"""
        response = await client.get("/api/v1/users/export-data", headers=auth_headers)
        assert response.status_code == 200
        
        exported_data = response.json()
        assert "user_profile" in exported_data
        assert "quotes" in exported_data
        assert "documents" in exported_data
        assert "activity_log" in exported_data
        assert "created_at" in exported_data["user_profile"]

    async def test_delete_user_data(self, client: AsyncClient):
        """Test deleting user data (GDPR compliance)"""
        # Create a separate user for deletion test
        user_data = {
            "email": "todelete@example.com",
            "username": "todelete",
            "password": "deletepassword123",
            "phone_number": "+1234567893",
            "company_name": "Delete Test Company"
        }
        
        # Register user
        register_response = await client.post("/api/v1/auth/register", json=user_data)
        assert register_response.status_code == 201
        
        # Login
        login_data = {
            "username": "todelete@example.com",
            "password": "deletepassword123"
        }
        
        login_response = await client.post("/api/v1/auth/login", data=login_data)
        delete_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        # Delete user data
        delete_data = {
            "password": "deletepassword123",
            "confirmation": "DELETE_MY_DATA"
        }
        
        response = await client.post("/api/v1/users/delete-data", json=delete_data, headers=delete_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "User data deleted successfully"

    async def test_admin_get_all_users(self, client: AsyncClient, admin_auth_headers: dict, test_user: User):
        """Test admin endpoint to get all users"""
        response = await client.get("/api/v1/users/admin/all", headers=admin_auth_headers)
        assert response.status_code == 200
        
        users = response.json()
        assert isinstance(users, list)
        assert len(users) >= 2  # At least test user and admin user
        
        # Check that sensitive data is not exposed
        for user in users:
            assert "password" not in user
            assert "hashed_password" not in user

    async def test_admin_get_all_users_unauthorized(self, client: AsyncClient, auth_headers: dict):
        """Test admin endpoint access by regular user"""
        response = await client.get("/api/v1/users/admin/all", headers=auth_headers)
        assert response.status_code == 403

    async def test_admin_get_user_by_id(self, client: AsyncClient, admin_auth_headers: dict, test_user: User):
        """Test admin endpoint to get specific user"""
        response = await client.get(f"/api/v1/users/admin/{test_user.id}", headers=admin_auth_headers)
        assert response.status_code == 200
        
        user_data = response.json()
        assert user_data["id"] == test_user.id
        assert user_data["email"] == test_user.email
        assert "password" not in user_data

    async def test_admin_update_user(self, client: AsyncClient, admin_auth_headers: dict, test_user: User):
        """Test admin updating user account"""
        update_data = {
            "is_active": False,
            "is_verified": True,
            "notes": "Account suspended by admin"
        }
        
        response = await client.put(f"/api/v1/users/admin/{test_user.id}", json=update_data, headers=admin_auth_headers)
        assert response.status_code == 200
        
        updated_user = response.json()
        assert updated_user["is_active"] is False
        assert updated_user["is_verified"] is True

    async def test_admin_user_statistics(self, client: AsyncClient, admin_auth_headers: dict):
        """Test admin getting system-wide user statistics"""
        response = await client.get("/api/v1/users/admin/statistics", headers=admin_auth_headers)
        assert response.status_code == 200
        
        stats = response.json()
        assert "total_users" in stats
        assert "active_users" in stats
        assert "new_users_this_month" in stats
        assert "user_activity_summary" in stats
        assert stats["total_users"] >= 2

    async def test_user_quota_information(self, client: AsyncClient, auth_headers: dict):
        """Test getting user quota information"""
        response = await client.get("/api/v1/users/quota", headers=auth_headers)
        assert response.status_code == 200
        
        quota = response.json()
        assert "quotes_limit" in quota
        assert "quotes_used" in quota
        assert "documents_limit" in quota
        assert "documents_used" in quota
        assert "storage_limit" in quota
        assert "storage_used" in quota

    async def test_user_subscription_info(self, client: AsyncClient, auth_headers: dict):
        """Test getting user subscription information"""
        response = await client.get("/api/v1/users/subscription", headers=auth_headers)
        assert response.status_code == 200
        
        subscription = response.json()
        assert "plan_type" in subscription
        assert "status" in subscription
        assert "expires_at" in subscription or "trial_ends_at" in subscription

    async def test_user_notifications(self, client: AsyncClient, auth_headers: dict):
        """Test getting user notifications"""
        response = await client.get("/api/v1/users/notifications", headers=auth_headers)
        assert response.status_code == 200
        
        notifications = response.json()
        assert isinstance(notifications, list)
        
        # Each notification should have required fields
        for notification in notifications:
            assert "id" in notification
            assert "type" in notification
            assert "message" in notification
            assert "created_at" in notification
            assert "is_read" in notification

    async def test_mark_notification_as_read(self, client: AsyncClient, auth_headers: dict):
        """Test marking notification as read"""
        # First get notifications
        notifications_response = await client.get("/api/v1/users/notifications", headers=auth_headers)
        notifications = notifications_response.json()
        
        if notifications:
            notification_id = notifications[0]["id"]
            
            response = await client.put(f"/api/v1/users/notifications/{notification_id}/read", headers=auth_headers)
            assert response.status_code == 200
            
            # Verify notification is marked as read
            updated_response = await client.get("/api/v1/users/notifications", headers=auth_headers)
            updated_notifications = updated_response.json()
            
            updated_notification = next((n for n in updated_notifications if n["id"] == notification_id), None)
            if updated_notification:
                assert updated_notification["is_read"] is True

    async def test_user_preferences(self, client: AsyncClient, auth_headers: dict):
        """Test getting and updating user preferences"""
        # Get current preferences
        get_response = await client.get("/api/v1/users/preferences", headers=auth_headers)
        assert get_response.status_code == 200
        
        preferences = get_response.json()
        assert "default_paint_type" in preferences
        assert "default_currency" in preferences
        assert "measurement_unit" in preferences
        
        # Update preferences
        update_data = {
            "default_paint_type": "Premium",
            "default_currency": "EUR",
            "measurement_unit": "metric",
            "auto_save_quotes": True
        }
        
        put_response = await client.put("/api/v1/users/preferences", json=update_data, headers=auth_headers)
        assert put_response.status_code == 200
        
        updated_preferences = put_response.json()
        assert updated_preferences["default_paint_type"] == "Premium"
        assert updated_preferences["default_currency"] == "EUR"
        assert updated_preferences["auto_save_quotes"] is True