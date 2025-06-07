from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List

from src.core.database import get_db
from src.routes.auth import get_current_user
from src.models.models import User
from src.schemas.schemas import UserResponse, UserUpdate, SuccessResponse

router = APIRouter()

@router.get("/profile", response_model=UserResponse)
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return current_user

@router.put("/profile", response_model=UserResponse)
async def update_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user profile"""
    
    # Check if username/email is already taken by another user
    if user_update.username or user_update.email:
        conditions = []
        if user_update.username:
            conditions.append(User.username == user_update.username)
        if user_update.email:
            conditions.append(User.email == user_update.email)
        
        result = await db.execute(
            select(User).where(
                (conditions[0] if len(conditions) == 1 else conditions[0] | conditions[1]) &
                (User.id != current_user.id)
            )
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already taken"
            )
    
    # Update user
    update_data = user_update.model_dump(exclude_unset=True)
    if update_data:
        await db.execute(
            update(User).where(User.id == current_user.id).values(**update_data)
        )
        await db.commit()
        
        # Refresh user data
        await db.refresh(current_user)
    
    return current_user

@router.delete("/profile", response_model=SuccessResponse)
async def delete_user_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete current user account"""
    
    await db.delete(current_user)
    await db.commit()
    
    return SuccessResponse(message="Account deleted successfully")

@router.get("/quota", response_model=dict)
async def get_user_quota(current_user: User = Depends(get_current_user)):
    """Get current user quota information"""
    
    total_available = 3  # Free tier
    if current_user.is_premium:
        total_available = -1  # Unlimited
    
    quotes_remaining = max(0, total_available - current_user.quotes_this_month) if total_available > 0 else -1
    
    return {
        "is_premium": current_user.is_premium,
        "unlimited": current_user.is_premium,
        "total_available": total_available,
        "quotes_used": current_user.quotes_this_month,
        "quotes_remaining": quotes_remaining,
        "additional_quotes": current_user.additional_quotes
    }

