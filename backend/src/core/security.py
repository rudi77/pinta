from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import uuid
import logging
from core.settings import settings
from core.cache import cache_service

logger = logging.getLogger(__name__)

# Security configuration
ALGORITHM = "HS256"

# Password hashing with configurable rounds
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.bcrypt_rounds)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token with JTI for blacklisting"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    
    # Add unique JTI (JWT ID) for token blacklisting
    jti = str(uuid.uuid4())
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "jti": jti
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token with JTI for blacklisting"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    
    # Add unique JTI for token blacklisting
    jti = str(uuid.uuid4())
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": jti
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt

def create_token_pair(user_data: dict) -> Dict[str, str]:
    """Create both access and refresh tokens"""
    access_token = create_access_token(user_data)
    refresh_token = create_refresh_token(user_data)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60
    }

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token with blacklist check"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        
        # Check if token is blacklisted
        jti = payload.get("jti")
        if jti and is_token_blacklisted(jti):
            logger.warning(f"Attempted use of blacklisted token: {jti}")
            return None
        
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None

def verify_refresh_token(token: str) -> Optional[dict]:
    """Verify refresh token specifically"""
    payload = verify_token(token)
    if payload and payload.get("type") == "refresh":
        return payload
    return None

async def blacklist_token(token: str) -> bool:
    """Add token to blacklist"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")
        
        if not jti or not exp:
            return False
        
        # Calculate TTL until token expires
        expire_time = datetime.fromtimestamp(exp, timezone.utc)
        ttl = int((expire_time - datetime.now(timezone.utc)).total_seconds())
        
        if ttl > 0:
            # Store in Redis with TTL
            key = f"blacklist:{jti}"
            await cache_service.redis_client.setex(key, ttl, "blacklisted")
            logger.info(f"Token blacklisted: {jti}")
        
        return True
    except Exception as e:
        logger.error(f"Error blacklisting token: {e}")
        return False

def is_token_blacklisted(jti: str) -> bool:
    """Check if token is blacklisted (synchronous for FastAPI dependencies)"""
    try:
        if not cache_service.enabled or not cache_service.redis_client:
            return False
        
        key = f"blacklist:{jti}"
        # Use sync redis client for this check
        import redis
        sync_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        return sync_client.exists(key) > 0
    except Exception as e:
        logger.warning(f"Error checking blacklist: {e}")
        return False  # Fail open for availability

async def cleanup_expired_blacklist():
    """Cleanup expired blacklisted tokens (runs periodically)"""
    try:
        if not cache_service.enabled:
            return
        
        # Redis automatically expires keys, but we can clean up manually if needed
        pattern = "blacklist:*"
        keys = await cache_service.redis_client.keys(pattern)
        
        expired_count = 0
        for key in keys:
            ttl = await cache_service.redis_client.ttl(key)
            if ttl <= 0:  # Expired or no TTL
                await cache_service.redis_client.delete(key)
                expired_count += 1
        
        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired blacklisted tokens")
            
    except Exception as e:
        logger.error(f"Error cleaning up blacklist: {e}")

async def revoke_all_user_tokens(user_id: int):
    """Revoke all tokens for a specific user"""
    try:
        # Add user to revoked list with current timestamp
        revoke_time = datetime.now(timezone.utc).timestamp()
        key = f"user_revoked:{user_id}"
        
        # Store revocation time for 7 days (max refresh token lifetime)
        ttl = settings.refresh_token_expire_days * 24 * 3600
        await cache_service.redis_client.setex(key, ttl, str(revoke_time))
        
        logger.info(f"All tokens revoked for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error revoking user tokens: {e}")
        return False

def is_user_tokens_revoked(user_id: int, issued_at: float) -> bool:
    """Check if user tokens were revoked after this token was issued"""
    try:
        if not cache_service.enabled:
            return False
        
        key = f"user_revoked:{user_id}"
        import redis
        sync_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        
        revoke_time = sync_client.get(key)
        if revoke_time:
            revoke_timestamp = float(revoke_time)
            return issued_at < revoke_timestamp
        
        return False
    except Exception as e:
        logger.warning(f"Error checking user token revocation: {e}")
        return False


# FastAPI dependencies
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from models.models import User

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user with enhanced security checks"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
        
        # Verify token type
        if payload.get("type") != "access":
            logger.warning(f"Invalid token type: {payload.get('type')}")
            raise credentials_exception
            
        email: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        issued_at: float = payload.get("iat", 0)
        
        if email is None or user_id is None:
            raise credentials_exception
        
        # Check if user tokens were revoked
        if is_user_tokens_revoked(user_id, issued_at):
            logger.info(f"Using revoked token for user {user_id}")
            raise credentials_exception
            
    except JWTError as e:
        logger.warning(f"JWT error: {e}")
        raise credentials_exception
    
    # Get user from database
    result = await db.execute(select(User).where(User.id == user_id, User.email == email))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
        
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")
    return current_user

async def get_refresh_token_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Validate refresh token and get user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = verify_refresh_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
            
        email: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        issued_at: float = payload.get("iat", 0)
        
        if email is None or user_id is None:
            raise credentials_exception
        
        # Check if user tokens were revoked
        if is_user_tokens_revoked(user_id, issued_at):
            logger.info(f"Using revoked refresh token for user {user_id}")
            raise credentials_exception
            
    except JWTError as e:
        logger.warning(f"Refresh token error: {e}")
        raise credentials_exception
    
    # Get user from database
    result = await db.execute(select(User).where(User.id == user_id, User.email == email))
    user = result.scalar_one_or_none()
    
    if user is None or not user.is_active:
        raise credentials_exception
        
    return user

# Rate limiting dependency
async def check_auth_rate_limit(
    request,  # FastAPI Request object
    db: AsyncSession = Depends(get_db)
) -> bool:
    """Check authentication rate limiting"""
    try:
        # Get client IP
        client_ip = request.client.host
        
        # Check rate limit
        rate_count = await cache_service.increment_rate_limit(
            f"auth:{client_ip}", 
            settings.rate_limit_window_minutes * 60
        )
        
        if rate_count > settings.rate_limit_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many authentication attempts. Try again in {settings.rate_limit_window_minutes} minutes.",
                headers={"Retry-After": str(settings.rate_limit_window_minutes * 60)}
            )
        
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        return True  # Fail open for availability

