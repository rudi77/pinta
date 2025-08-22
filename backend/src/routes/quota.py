from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, desc
from typing import Optional, List, Dict
from datetime import datetime, timedelta, timezone

from src.core.database import get_db
from src.core.security import get_current_user, get_current_active_user
from src.services.quota_service import QuotaService
from src.models.models import User, UsageTracking, QuotaNotification
from src.schemas.schemas import SuccessResponse

router = APIRouter(prefix="/api/v1/quota", tags=["quota"])
quota_service = QuotaService()

@router.get("/status")
async def get_quota_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive quota status for current user"""
    
    try:
        quota_status = await quota_service.get_user_quota_status(current_user, db)
        return {
            "success": True,
            "quota_status": quota_status
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get quota status: {str(e)}"
        )

@router.post("/check")
async def check_quota(
    resource_type: str,
    amount: int = 1,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Check if user can consume specific quota without actually consuming it"""
    
    if resource_type not in ['quotes', 'documents', 'api_requests', 'storage']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid resource type. Must be one of: quotes, documents, api_requests, storage"
        )
    
    try:
        # Get current quota status
        quota_status = await quota_service.get_user_quota_status(current_user, db)
        usage = quota_status['usage']
        
        if resource_type in usage:
            resource_usage = usage[resource_type]
            can_consume = resource_usage['remaining'] >= amount or resource_usage['limit'] == -1
            
            return {
                "success": True,
                "can_consume": can_consume,
                "resource_type": resource_type,
                "requested_amount": amount,
                "current_usage": resource_usage
            }
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Resource type {resource_type} not found in quota status"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check quota: {str(e)}"
        )

@router.post("/consume")
async def consume_quota(
    resource_type: str,
    amount: int = 1,
    metadata: Optional[Dict] = None,
    request: Request = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Consume quota for a specific resource type"""
    
    if resource_type not in ['quotes', 'documents', 'api_requests', 'storage']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid resource type"
        )
    
    try:
        # Check and consume quota
        allowed, result_info = await quota_service.check_quota_and_consume(
            current_user, resource_type, db, amount
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=result_info
            )
        
        # Track usage
        await _track_usage(
            user_id=current_user.id,
            resource_type=resource_type,
            action=f"consume_{resource_type}",
            amount=amount,
            metadata=metadata,
            request=request,
            db=db
        )
        
        return {
            "success": True,
            "consumed": amount,
            "resource_type": resource_type,
            "result": result_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to consume quota: {str(e)}"
        )

@router.get("/analytics")
async def get_quota_analytics(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed quota usage analytics"""
    
    if days < 1 or days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Days must be between 1 and 365"
        )
    
    try:
        analytics = await quota_service.get_quota_analytics(current_user, db, days)
        return {
            "success": True,
            "analytics": analytics
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analytics: {str(e)}"
        )

@router.get("/usage-history")
async def get_usage_history(
    resource_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get usage history for the user"""
    
    if limit > 100:
        limit = 100
    
    try:
        query = select(UsageTracking).where(UsageTracking.user_id == current_user.id)
        
        if resource_type:
            query = query.where(UsageTracking.resource_type == resource_type)
        
        query = query.order_by(desc(UsageTracking.created_at)).limit(limit).offset(offset)
        
        result = await db.execute(query)
        usage_records = result.scalars().all()
        
        return {
            "success": True,
            "usage_history": [
                {
                    "id": record.id,
                    "resource_type": record.resource_type,
                    "action": record.action,
                    "amount": record.amount,
                    "metadata": record.metadata,
                    "created_at": record.created_at.isoformat(),
                    "ip_address": record.ip_address
                }
                for record in usage_records
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "returned_count": len(usage_records)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get usage history: {str(e)}"
        )

@router.get("/notifications")
async def get_quota_notifications(
    unread_only: bool = False,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get quota notifications for the user"""
    
    try:
        query = select(QuotaNotification).where(QuotaNotification.user_id == current_user.id)
        
        if unread_only:
            query = query.where(QuotaNotification.is_read == False)
        
        query = query.order_by(desc(QuotaNotification.created_at)).limit(limit)
        
        result = await db.execute(query)
        notifications = result.scalars().all()
        
        return {
            "success": True,
            "notifications": [
                {
                    "id": notification.id,
                    "notification_type": notification.notification_type,
                    "resource_type": notification.resource_type,
                    "threshold_percentage": notification.threshold_percentage,
                    "message": notification.message,
                    "is_read": notification.is_read,
                    "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
                    "created_at": notification.created_at.isoformat()
                }
                for notification in notifications
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notifications: {str(e)}"
        )

@router.post("/notifications/{notification_id}/mark-read", response_model=SuccessResponse)
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a notification as read"""
    
    try:
        result = await db.execute(
            update(QuotaNotification)
            .where(and_(
                QuotaNotification.id == notification_id,
                QuotaNotification.user_id == current_user.id
            ))
            .values(is_read=True)
        )
        
        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        await db.commit()
        
        return SuccessResponse(message="Notification marked as read")
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark notification as read: {str(e)}"
        )

@router.post("/notifications/mark-all-read", response_model=SuccessResponse)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark all notifications as read for the user"""
    
    try:
        await db.execute(
            update(QuotaNotification)
            .where(QuotaNotification.user_id == current_user.id)
            .values(is_read=True)
        )
        
        await db.commit()
        
        return SuccessResponse(message="All notifications marked as read")
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark all notifications as read: {str(e)}"
        )

@router.put("/settings")
async def update_quota_settings(
    quota_warnings_enabled: Optional[bool] = None,
    quota_notification_threshold: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user quota notification settings"""
    
    try:
        update_data = {}
        
        if quota_warnings_enabled is not None:
            update_data['quota_warnings_enabled'] = quota_warnings_enabled
        
        if quota_notification_threshold is not None:
            if quota_notification_threshold < 50 or quota_notification_threshold > 100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Notification threshold must be between 50 and 100"
                )
            update_data['quota_notification_threshold'] = quota_notification_threshold
        
        if update_data:
            await db.execute(
                update(User)
                .where(User.id == current_user.id)
                .values(**update_data)
            )
            await db.commit()
            await db.refresh(current_user)
        
        return {
            "success": True,
            "message": "Quota settings updated",
            "settings": {
                "quota_warnings_enabled": current_user.quota_warnings_enabled,
                "quota_notification_threshold": current_user.quota_notification_threshold
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update quota settings: {str(e)}"
        )

# Helper functions

async def _track_usage(
    user_id: int,
    resource_type: str,
    action: str,
    amount: int,
    metadata: Optional[Dict],
    request: Optional[Request],
    db: AsyncSession
):
    """Track usage in the database"""
    
    try:
        import json
        
        # Get request details
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get('user-agent', '')[:500]
        
        usage_record = UsageTracking(
            user_id=user_id,
            resource_type=resource_type,
            action=action,
            amount=amount,
            metadata=json.dumps(metadata) if metadata else None,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(usage_record)
        await db.commit()
        
    except Exception as e:
        # Don't fail the main operation if tracking fails
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to track usage for user {user_id}: {e}")
        await db.rollback()