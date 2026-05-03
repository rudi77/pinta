from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional
from datetime import datetime, timedelta, timezone
import logging
import secrets

from src.core.database import get_db
from src.core.security import (
    verify_password, get_password_hash, create_token_pair,
    blacklist_token, revoke_all_user_tokens,
    get_current_user, get_current_active_user, get_refresh_token_user,
    check_auth_rate_limit
)
from src.core.settings import settings
from src.models.models import User, EmailVerificationToken
from src.schemas.schemas import UserCreate, UserResponse, LoginRequest, Token, SuccessResponse
from src.services.email_service import email_service

VERIFICATION_TOKEN_TTL_HOURS = 24


async def _issue_verification_token(user: User, db: AsyncSession) -> EmailVerificationToken:
    """Create and persist a fresh verification token for `user`."""
    token = EmailVerificationToken(
        user_id=user.id,
        token=secrets.token_urlsafe(48),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=VERIFICATION_TOKEN_TTL_HOURS),
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


def _verification_url(token: str) -> str:
    base = settings.app_base_url.rstrip("/")
    return f"{base}/verify-email?token={token}"


def _local_dev_auth_enabled(request: Request) -> bool:
    """Allow frictionless auth only for local development."""
    client_host = request.client.host if request.client else ""
    return settings.debug or (
        not settings.smtp_host and client_host in {"127.0.0.1", "::1", "localhost"}
    )

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
    
    # Create new user with enhanced security. Local dev without SMTP auto-
    # verifies so the app is usable; production requires an emailed link.
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        company_name=user_data.company_name,
        phone=user_data.phone,
        address=user_data.address,
        is_active=True,
        is_verified=_local_dev_auth_enabled(request),
    )

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    logger.info(f"User registered successfully: {db_user.email} (ID: {db_user.id})")

    if not db_user.is_verified:
        token_row = await _issue_verification_token(db_user, db)
        await email_service.send_verification_email(
            db_user.email, _verification_url(token_row.token)
        )

    return {
        "id": db_user.id,
        "email": db_user.email,
        "username": db_user.username,
        "is_verified": db_user.is_verified,
    }


@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    """Activate a user by confirming ownership of their email address."""
    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token == token)
    )
    row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    if row.used_at is not None:
        raise HTTPException(status_code=400, detail="Verification token already used")

    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification token expired")

    now = datetime.now(timezone.utc)
    await db.execute(
        update(User).where(User.id == row.user_id).values(is_verified=True)
    )
    await db.execute(
        update(EmailVerificationToken)
        .where(EmailVerificationToken.id == row.id)
        .values(used_at=now)
    )
    await db.commit()

    logger.info(f"Email verified for user_id={row.user_id}")
    return SuccessResponse(message="Email verified successfully")


@router.post("/resend-verification", response_model=SuccessResponse)
async def resend_verification(
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Resend verification email. Generic success to avoid user-enumeration."""
    await check_auth_rate_limit(request, db)
    email = (payload or {}).get("email", "").strip().lower()
    generic = SuccessResponse(
        message="If the account exists and is not verified, a new email has been sent."
    )
    if not email:
        return generic

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or user.is_verified:
        return generic

    token_row = await _issue_verification_token(user, db)
    await email_service.send_verification_email(
        user.email, _verification_url(token_row.token)
    )
    return generic

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

    if not user.is_verified:
        logger.warning(f"Login attempt for unverified user: {login_data.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your inbox for the verification link."
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


@router.post("/demo-login")
async def demo_login(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Issue a real token for the local demo user.

    This is intentionally limited to debug/local-without-SMTP setups so the
    web demo exercises the authenticated backend instead of faking auth state.
    """
    if not _local_dev_auth_enabled(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo login is only available in local development.",
        )

    email = "demo@example.com"
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        username_result = await db.execute(select(User).where(User.username == "demo"))
        username = (
            "demo"
            if username_result.scalar_one_or_none() is None
            else f"demo-{secrets.token_hex(4)}"
        )
        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            company_name="Demo Malerbetrieb",
            is_active=True,
            is_verified=True,
            is_premium=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        user.is_active = True
        user.is_verified = True
        user.is_premium = True
        if not user.company_name:
            user.company_name = "Demo Malerbetrieb"
        await db.commit()
        await db.refresh(user)

    return create_token_pair({
        "sub": user.email,
        "user_id": user.id,
        "username": user.username,
    })

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

