from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import logging

from src.core.database import get_db
from src.core.security import (
    verify_password, get_password_hash, create_token_pair, 
    blacklist_token, revoke_all_user_tokens,
    get_current_user, get_current_active_user, get_refresh_token_user,
    check_auth_rate_limit
)
from src.models.models import User
from src.schemas.schemas import UserCreate, UserResponse, LoginRequest, Token, SuccessResponse

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
security = HTTPBearer()
logger = logging.getLogger(__name__)

@router.post("/register", status_code=201)
async def register(
    user_data: UserCreate, 
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user with rate limiting"""
    
    # Check rate limiting
    await check_auth_rate_limit(request, db)
    
    logger.info(f"Registration attempt for email: {user_data.email}")
    
    # Check if user already exists
    result = await db.execute(
        select(User).where(
            (User.email == user_data.email) | (User.username == user_data.username)
        )
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        if existing_user.email == user_data.email:
            detail = "User with this email already exists"
        else:
            detail = "Username already taken"
        
        logger.warning(f"Registration failed - user exists: {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )
    
    # Create new user with enhanced security
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        company_name=user_data.company_name,
        phone=user_data.phone,
        address=user_data.address,
        is_active=True  # Account active by default
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    logger.info(f"User registered successfully: {db_user.email} (ID: {db_user.id})")
    
    return {
        "id": db_user.id,
        "email": db_user.email,
        "username": db_user.username
    }

@router.post("/login")
async def login(
    login_data: LoginRequest, 
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return token pair with rate limiting"""
    
    # Check rate limiting
    await check_auth_rate_limit(request, db)
    
    logger.info(f"Login attempt for email: {login_data.email}")
    
    # Get user by email
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for email: {login_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        logger.warning(f"Login attempt for inactive user: {login_data.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated"
        )
    
    # Create token pair with user data
    user_data = {
        "sub": user.email,
        "user_id": user.id,
        "username": user.username
    }
    
    tokens = create_token_pair(user_data)
    
    logger.info(f"Successful login for user: {user.email} (ID: {user.id})")
    
    return tokens

@router.post("/refresh")
async def refresh_token(
    current_user: User = Depends(get_refresh_token_user)
):
    """Refresh access token using refresh token"""
    
    logger.info(f"Token refresh for user: {current_user.email}")
    
    # Create new token pair
    user_data = {
        "sub": current_user.email,
        "user_id": current_user.id,
        "username": current_user.username
    }
    
    tokens = create_token_pair(user_data)
    
    return tokens

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    return current_user

@router.post("/logout", response_model=SuccessResponse)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_active_user)
):
    """Logout user and blacklist current token"""
    
    try:
        # Blacklist the current access token
        await blacklist_token(credentials.credentials)
        logger.info(f"User logged out: {current_user.email}")
        
        return SuccessResponse(message="Logged out successfully")
    except Exception as e:
        logger.error(f"Logout error for user {current_user.email}: {e}")
        return SuccessResponse(message="Logged out successfully")  # Don't reveal errors

@router.post("/logout-all", response_model=SuccessResponse)
async def logout_all_devices(
    current_user: User = Depends(get_current_active_user)
):
    """Logout user from all devices by revoking all tokens"""
    
    try:
        # Revoke all user tokens
        await revoke_all_user_tokens(current_user.id)
        logger.info(f"All tokens revoked for user: {current_user.email}")
        
        return SuccessResponse(message="Logged out from all devices")
    except Exception as e:
        logger.error(f"Logout all devices error for user {current_user.email}: {e}")
        return SuccessResponse(message="Logged out from all devices")  # Don't reveal errors

@router.post("/change-password", response_model=SuccessResponse)
async def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password and revoke all existing tokens"""
    
    # Verify old password
    if not verify_password(old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Validate new password strength (basic validation)
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(new_password)
    await db.commit()
    
    # Revoke all existing tokens to force re-login
    await revoke_all_user_tokens(current_user.id)
    
    logger.info(f"Password changed for user: {current_user.email}")
    
    return SuccessResponse(message="Password changed successfully. Please log in again.")

@router.get("/security-info")
async def get_security_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get security information for current user"""
    
    return {
        "user_id": current_user.id,
        "account_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "token_expires_in_minutes": 15,  # Access token expiry
        "refresh_expires_in_days": 7     # Refresh token expiry
    }

