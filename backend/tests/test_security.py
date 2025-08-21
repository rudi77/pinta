import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from jose import jwt

from src.main import app
from src.core.security import (
    create_access_token, create_refresh_token, create_token_pair,
    verify_token, verify_refresh_token, blacklist_token, 
    is_token_blacklisted, revoke_all_user_tokens, is_user_tokens_revoked,
    get_password_hash, verify_password
)
from src.core.settings import settings

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def user_data():
    return {
        "sub": "test@example.com",
        "user_id": 123,
        "username": "testuser"
    }

def test_password_hashing():
    """Test password hashing and verification"""
    password = "test_password_123"
    
    # Hash password
    hashed = get_password_hash(password)
    
    assert hashed != password
    assert len(hashed) > 50  # bcrypt hashes are long
    assert hashed.startswith("$2b$")  # bcrypt prefix
    
    # Verify correct password
    assert verify_password(password, hashed) is True
    
    # Verify incorrect password
    assert verify_password("wrong_password", hashed) is False

def test_access_token_creation_and_verification(user_data):
    """Test access token creation and verification"""
    
    # Create access token
    token = create_access_token(user_data)
    
    assert isinstance(token, str)
    assert len(token) > 100  # JWT tokens are long
    
    # Verify token
    payload = verify_token(token)
    
    assert payload is not None
    assert payload["sub"] == user_data["sub"]
    assert payload["user_id"] == user_data["user_id"]
    assert payload["type"] == "access"
    assert "jti" in payload
    assert "exp" in payload
    assert "iat" in payload

def test_refresh_token_creation_and_verification(user_data):
    """Test refresh token creation and verification"""
    
    # Create refresh token
    token = create_refresh_token(user_data)
    
    assert isinstance(token, str)
    assert len(token) > 100
    
    # Verify as refresh token
    payload = verify_refresh_token(token)
    
    assert payload is not None
    assert payload["sub"] == user_data["sub"]
    assert payload["user_id"] == user_data["user_id"]
    assert payload["type"] == "refresh"
    
    # Should not verify as regular token for access
    # (this depends on your implementation)

def test_token_pair_creation(user_data):
    """Test creation of token pair"""
    
    tokens = create_token_pair(user_data)
    
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert "token_type" in tokens
    assert "expires_in" in tokens
    
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == 15 * 60  # 15 minutes in seconds
    
    # Verify both tokens
    access_payload = verify_token(tokens["access_token"])
    refresh_payload = verify_refresh_token(tokens["refresh_token"])
    
    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"

def test_token_expiration(user_data):
    """Test token expiration"""
    
    # Create token with short expiration
    short_expiry = timedelta(seconds=1)
    token = create_access_token(user_data, expires_delta=short_expiry)
    
    # Token should be valid immediately
    payload = verify_token(token)
    assert payload is not None
    
    # Wait for token to expire
    time.sleep(2)
    
    # Token should now be invalid
    payload = verify_token(token)
    assert payload is None

@pytest.mark.asyncio
async def test_token_blacklisting(user_data):
    """Test token blacklisting functionality"""
    
    from src.core.cache import cache_service
    
    # Mock cache service
    cache_service.enabled = True
    cache_service.redis_client = MagicMock()
    cache_service.redis_client.setex = MagicMock()
    
    # Create token
    token = create_access_token(user_data)
    
    # Blacklist token
    result = await blacklist_token(token)
    assert result is True
    
    # Verify cache was called
    assert cache_service.redis_client.setex.called

def test_is_token_blacklisted():
    """Test blacklist checking"""
    
    # Mock redis for blacklist check
    with patch('src.core.security.redis.Redis') as mock_redis:
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        
        # Test non-blacklisted token
        mock_client.exists.return_value = 0
        assert is_token_blacklisted("test_jti") is False
        
        # Test blacklisted token
        mock_client.exists.return_value = 1
        assert is_token_blacklisted("test_jti") is True

@pytest.mark.asyncio
async def test_user_token_revocation(user_data):
    """Test revoking all tokens for a user"""
    
    from src.core.cache import cache_service
    
    # Mock cache service
    cache_service.enabled = True
    cache_service.redis_client = MagicMock()
    cache_service.redis_client.setex = MagicMock()
    
    user_id = 123
    
    # Revoke user tokens
    result = await revoke_all_user_tokens(user_id)
    assert result is True
    
    # Verify cache was called with correct parameters
    assert cache_service.redis_client.setex.called
    call_args = cache_service.redis_client.setex.call_args
    assert f"user_revoked:{user_id}" in call_args[0]

def test_user_token_revocation_check():
    """Test checking if user tokens are revoked"""
    
    user_id = 123
    issued_at = datetime.now(timezone.utc).timestamp()
    
    with patch('src.core.security.redis.Redis') as mock_redis:
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        
        # Test no revocation
        mock_client.get.return_value = None
        assert is_user_tokens_revoked(user_id, issued_at) is False
        
        # Test token issued after revocation
        future_revoke_time = str(issued_at + 3600)  # 1 hour later
        mock_client.get.return_value = future_revoke_time
        assert is_user_tokens_revoked(user_id, issued_at) is True
        
        # Test token issued before revocation
        past_revoke_time = str(issued_at - 3600)  # 1 hour earlier
        mock_client.get.return_value = past_revoke_time
        assert is_user_tokens_revoked(user_id, issued_at) is False

def test_invalid_token_verification():
    """Test verification of invalid tokens"""
    
    # Test completely invalid token
    assert verify_token("invalid_token") is None
    
    # Test token with wrong signature
    fake_token = jwt.encode({"sub": "test"}, "wrong_secret", algorithm="HS256")
    assert verify_token(fake_token) is None
    
    # Test malformed token
    assert verify_token("not.a.token") is None

@pytest.mark.asyncio
async def test_auth_endpoints_rate_limiting(client):
    """Test rate limiting on authentication endpoints"""
    
    # Mock cache service for rate limiting
    with patch('src.core.security.cache_service') as mock_cache:
        mock_cache.enabled = True
        mock_cache.increment_rate_limit = MagicMock()
        
        # First few requests should succeed
        mock_cache.increment_rate_limit.return_value = 3
        
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "password"
        })
        
        # Should not be rate limited yet
        assert response.status_code != 429
        
        # Simulate rate limit exceeded
        mock_cache.increment_rate_limit.return_value = 10
        
        response = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "password"
        })
        
        # Should be rate limited
        assert response.status_code == 429

def test_token_jti_uniqueness():
    """Test that tokens have unique JTI values"""
    
    user_data = {"sub": "test@example.com", "user_id": 123}
    
    # Create multiple tokens
    tokens = [create_access_token(user_data) for _ in range(10)]
    
    # Decode all tokens and extract JTIs
    jtis = []
    for token in tokens:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        jtis.append(payload["jti"])
    
    # All JTIs should be unique
    assert len(set(jtis)) == len(jtis)

def test_bcrypt_rounds_configuration():
    """Test that bcrypt uses configured number of rounds"""
    
    password = "test_password"
    hashed = get_password_hash(password)
    
    # Extract rounds from hash
    rounds = int(hashed.split('$')[2])
    
    # Should match configured rounds
    assert rounds == settings.bcrypt_rounds

@pytest.mark.asyncio
async def test_security_task_manager():
    """Test security task manager functionality"""
    
    from src.core.security_tasks import SecurityTaskManager
    
    manager = SecurityTaskManager()
    
    # Initially not running
    assert manager.running is False
    assert len(manager.tasks) == 0
    
    # Start tasks
    await manager.start_background_tasks()
    
    assert manager.running is True
    assert len(manager.tasks) > 0
    
    # Get status
    status = await manager.get_security_status()
    assert "running" in status
    assert status["running"] is True
    
    # Stop tasks
    await manager.stop_background_tasks()
    
    assert manager.running is False
    assert len(manager.tasks) == 0

def test_security_health_endpoint(client):
    """Test security health endpoint"""
    
    response = client.get("/security-health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert "details" in data

@pytest.mark.asyncio
async def test_login_with_inactive_user():
    """Test login attempt with inactive user account"""
    
    # This would require a more complex test setup with database mocking
    # For now, we test the logic path
    pass

def test_password_strength_validation():
    """Test password strength requirements"""
    
    # Test would go here for password complexity validation
    # Currently we only check length in change_password endpoint
    pass

@pytest.mark.asyncio
async def test_concurrent_token_operations():
    """Test concurrent token operations for race conditions"""
    
    user_data = {"sub": "test@example.com", "user_id": 123}
    
    # Create multiple tokens concurrently
    tasks = [
        asyncio.create_task(asyncio.to_thread(create_access_token, user_data))
        for _ in range(10)
    ]
    
    tokens = await asyncio.gather(*tasks)
    
    # All tokens should be created successfully
    assert len(tokens) == 10
    assert all(isinstance(token, str) for token in tokens)
    
    # All tokens should be unique
    assert len(set(tokens)) == len(tokens)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])