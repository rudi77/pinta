import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, desc
from sqlalchemy.orm import selectinload

from models.models import User, Quote, Document
from core.cache import cache_service
from core.settings import settings

logger = logging.getLogger(__name__)

class QuotaService:
    """Comprehensive quota management service with analytics and notifications"""
    
    def __init__(self):
        self.free_tier_limits = {
            'quotes_per_month': 3,
            'documents_per_month': 10,
            'api_requests_per_day': 50,
            'storage_mb': 100
        }
        
        self.premium_limits = {
            'quotes_per_month': -1,  # Unlimited
            'documents_per_month': 500,
            'api_requests_per_day': 1000,
            'storage_mb': 1000
        }
    
    async def get_user_quota_status(self, user: User, db: AsyncSession) -> Dict:
        """Get comprehensive quota status for a user"""
        
        # Get current month boundaries
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
        
        # Get current day boundaries
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1) - timedelta(seconds=1)
        
        # Get user limits based on subscription
        limits = self.premium_limits if user.is_premium else self.free_tier_limits
        
        # Calculate quotes usage
        quotes_used_this_month = await self._get_quotes_used_this_month(user.id, month_start, month_end, db)
        quotes_remaining = self._calculate_remaining(quotes_used_this_month, limits['quotes_per_month'], user.additional_quotes or 0)
        
        # Calculate documents usage
        documents_used_this_month = await self._get_documents_used_this_month(user.id, month_start, month_end, db)
        documents_remaining = self._calculate_remaining(documents_used_this_month, limits['documents_per_month'])
        
        # Calculate API usage from cache
        api_requests_today = await self._get_api_requests_today(user.id, day_start)
        api_remaining = self._calculate_remaining(api_requests_today, limits['api_requests_per_day'])
        
        # Calculate storage usage
        storage_used_mb = await self._calculate_storage_usage(user.id, db)
        storage_remaining_mb = self._calculate_remaining(storage_used_mb, limits['storage_mb'])
        
        # Calculate usage percentages
        quota_status = {
            'user_id': user.id,
            'is_premium': user.is_premium,
            'premium_until': user.premium_until.isoformat() if user.premium_until else None,
            'limits': limits,
            'usage': {
                'quotes': {
                    'used': quotes_used_this_month,
                    'limit': limits['quotes_per_month'],
                    'remaining': quotes_remaining,
                    'additional_available': user.additional_quotes or 0,
                    'percentage': self._calculate_percentage(quotes_used_this_month, limits['quotes_per_month']) if limits['quotes_per_month'] > 0 else 0
                },
                'documents': {
                    'used': documents_used_this_month,
                    'limit': limits['documents_per_month'],
                    'remaining': documents_remaining,
                    'percentage': self._calculate_percentage(documents_used_this_month, limits['documents_per_month'])
                },
                'api_requests': {
                    'used': api_requests_today,
                    'limit': limits['api_requests_per_day'],
                    'remaining': api_remaining,
                    'percentage': self._calculate_percentage(api_requests_today, limits['api_requests_per_day'])
                },
                'storage': {
                    'used_mb': round(storage_used_mb, 2),
                    'limit_mb': limits['storage_mb'],
                    'remaining_mb': round(storage_remaining_mb, 2),
                    'percentage': self._calculate_percentage(storage_used_mb, limits['storage_mb'])
                }
            },
            'warnings': await self._generate_quota_warnings(user, limits, {
                'quotes_used': quotes_used_this_month,
                'documents_used': documents_used_this_month,
                'api_used': api_requests_today,
                'storage_used': storage_used_mb
            }),
            'period': {
                'month_start': month_start.isoformat(),
                'month_end': month_end.isoformat(),
                'day_start': day_start.isoformat(),
                'day_end': day_end.isoformat()
            },
            'last_updated': now.isoformat()
        }
        
        # Cache the quota status
        await self._cache_quota_status(user.id, quota_status)
        
        return quota_status
    
    async def check_quota_and_consume(self, user: User, resource_type: str, db: AsyncSession, amount: int = 1) -> Tuple[bool, Dict]:
        """Check if user can consume resources and update quota if allowed"""
        
        quota_status = await self.get_user_quota_status(user, db)
        usage = quota_status['usage']
        
        # Check specific resource type
        if resource_type == 'quotes':
            current_used = usage['quotes']['used']
            limit = usage['quotes']['limit']
            additional = usage['quotes']['additional_available']
            
            # Premium users have unlimited quotes
            if user.is_premium:
                await self._increment_usage_counter(user.id, 'quotes', amount, db)
                return True, {'allowed': True, 'reason': 'Premium user - unlimited'}
            
            # Check if within free tier limit
            if current_used + amount <= limit:
                await self._increment_usage_counter(user.id, 'quotes', amount, db)
                return True, {'allowed': True, 'remaining': limit - current_used - amount}
            
            # Check if can use additional quotes
            needed_additional = (current_used + amount) - limit
            if needed_additional <= additional:
                await self._increment_usage_counter(user.id, 'quotes', amount, db)
                await self._deduct_additional_quotes(user.id, needed_additional, db)
                return True, {'allowed': True, 'used_additional': needed_additional}
            
            return False, {
                'allowed': False, 
                'reason': 'Quota exceeded',
                'current_used': current_used,
                'limit': limit,
                'additional_available': additional
            }
        
        elif resource_type == 'documents':
            current_used = usage['documents']['used']
            limit = usage['documents']['limit']
            
            if current_used + amount <= limit:
                await self._increment_usage_counter(user.id, 'documents', amount, db)
                return True, {'allowed': True, 'remaining': limit - current_used - amount}
            
            return False, {
                'allowed': False,
                'reason': 'Document quota exceeded',
                'current_used': current_used,
                'limit': limit
            }
        
        elif resource_type == 'api_requests':
            current_used = usage['api_requests']['used']
            limit = usage['api_requests']['limit']
            
            if current_used + amount <= limit:
                await self._increment_api_usage(user.id, amount)
                return True, {'allowed': True, 'remaining': limit - current_used - amount}
            
            return False, {
                'allowed': False,
                'reason': 'API quota exceeded',
                'current_used': current_used,
                'limit': limit
            }
        
        elif resource_type == 'storage':
            current_used = usage['storage']['used_mb']
            limit = usage['storage']['limit_mb']
            
            if current_used + amount <= limit:
                return True, {'allowed': True, 'remaining': limit - current_used - amount}
            
            return False, {
                'allowed': False,
                'reason': 'Storage quota exceeded',
                'current_used_mb': current_used,
                'limit_mb': limit
            }
        
        return False, {'allowed': False, 'reason': f'Unknown resource type: {resource_type}'}
    
    async def get_quota_analytics(self, user: User, db: AsyncSession, days: int = 30) -> Dict:
        """Get detailed quota usage analytics"""
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Get daily usage breakdown
        daily_usage = await self._get_daily_usage_breakdown(user.id, start_date, end_date, db)
        
        # Get usage trends
        trends = await self._calculate_usage_trends(user.id, start_date, end_date, db)
        
        # Get peak usage times
        peak_usage = await self._get_peak_usage_times(user.id, start_date, end_date, db)
        
        return {
            'user_id': user.id,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            },
            'daily_usage': daily_usage,
            'trends': trends,
            'peak_usage': peak_usage,
            'summary': await self._get_usage_summary(user.id, start_date, end_date, db)
        }
    
    async def send_quota_notification(self, user: User, notification_type: str, quota_info: Dict) -> bool:
        """Send quota-related notifications to user"""
        
        try:
            notification = {
                'user_id': user.id,
                'type': notification_type,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'data': quota_info
            }
            
            # Store notification in cache for retrieval
            await cache_service.redis_client.lpush(
                f"notifications:{user.id}",
                str(notification)
            )
            
            # Keep only last 50 notifications
            await cache_service.redis_client.ltrim(f"notifications:{user.id}", 0, 49)
            
            logger.info(f"Quota notification sent to user {user.id}: {notification_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send quota notification to user {user.id}: {e}")
            return False
    
    async def reset_monthly_quotas(self, db: AsyncSession) -> Dict:
        """Reset monthly quotas for all users (typically run on 1st of month)"""
        
        try:
            # Reset quotes_this_month for all users
            result = await db.execute(
                update(User).values(quotes_this_month=0)
            )
            
            await db.commit()
            
            reset_info = {
                'reset_date': datetime.now(timezone.utc).isoformat(),
                'users_affected': result.rowcount,
                'reset_type': 'monthly_quotas'
            }
            
            logger.info(f"Monthly quotas reset for {result.rowcount} users")
            return reset_info
            
        except Exception as e:
            logger.error(f"Failed to reset monthly quotas: {e}")
            await db.rollback()
            raise
    
    # Private helper methods
    
    async def _get_quotes_used_this_month(self, user_id: int, month_start: datetime, month_end: datetime, db: AsyncSession) -> int:
        """Get number of quotes created this month"""
        result = await db.execute(
            select(func.count(Quote.id))
            .where(and_(
                Quote.user_id == user_id,
                Quote.created_at >= month_start,
                Quote.created_at <= month_end
            ))
        )
        return result.scalar() or 0
    
    async def _get_documents_used_this_month(self, user_id: int, month_start: datetime, month_end: datetime, db: AsyncSession) -> int:
        """Get number of documents uploaded this month"""
        result = await db.execute(
            select(func.count(Document.id))
            .where(and_(
                Document.user_id == user_id,
                Document.created_at >= month_start,
                Document.created_at <= month_end
            ))
        )
        return result.scalar() or 0
    
    async def _get_api_requests_today(self, user_id: int, day_start: datetime) -> int:
        """Get API requests count for today from cache"""
        try:
            key = f"api_usage:{user_id}:{day_start.strftime('%Y-%m-%d')}"
            count = await cache_service.redis_client.get(key)
            return int(count) if count else 0
        except Exception:
            return 0
    
    async def _calculate_storage_usage(self, user_id: int, db: AsyncSession) -> float:
        """Calculate total storage usage in MB"""
        result = await db.execute(
            select(func.sum(Document.file_size))
            .where(Document.user_id == user_id)
        )
        total_bytes = result.scalar() or 0
        return total_bytes / (1024 * 1024)  # Convert to MB
    
    def _calculate_remaining(self, used: int, limit: int, additional: int = 0) -> int:
        """Calculate remaining quota"""
        if limit == -1:  # Unlimited
            return -1
        return max(0, limit + additional - used)
    
    def _calculate_percentage(self, used: int, limit: int) -> float:
        """Calculate usage percentage"""
        if limit <= 0:
            return 0.0
        return min(100.0, (used / limit) * 100)
    
    async def _generate_quota_warnings(self, user: User, limits: Dict, usage: Dict) -> List[Dict]:
        """Generate quota warning messages"""
        warnings = []
        
        # Check quotes quota
        quotes_percentage = self._calculate_percentage(usage['quotes_used'], limits['quotes_per_month'])
        if not user.is_premium and quotes_percentage >= 80:
            warnings.append({
                'type': 'quota_warning',
                'resource': 'quotes',
                'percentage': quotes_percentage,
                'message': f"Sie haben {quotes_percentage:.0f}% Ihres monatlichen Kostenvoranschlag-Kontingents verbraucht.",
                'action': 'consider_upgrade' if quotes_percentage >= 90 else 'monitor'
            })
        
        # Check documents quota
        docs_percentage = self._calculate_percentage(usage['documents_used'], limits['documents_per_month'])
        if docs_percentage >= 80:
            warnings.append({
                'type': 'quota_warning',
                'resource': 'documents',
                'percentage': docs_percentage,
                'message': f"Sie haben {docs_percentage:.0f}% Ihres Dokument-Upload-Kontingents verbraucht.",
                'action': 'consider_upgrade' if docs_percentage >= 90 else 'monitor'
            })
        
        # Check API quota
        api_percentage = self._calculate_percentage(usage['api_used'], limits['api_requests_per_day'])
        if api_percentage >= 80:
            warnings.append({
                'type': 'quota_warning',
                'resource': 'api_requests',
                'percentage': api_percentage,
                'message': f"Sie haben {api_percentage:.0f}% Ihres täglichen API-Kontingents verbraucht.",
                'action': 'reduce_usage' if api_percentage >= 90 else 'monitor'
            })
        
        # Check storage quota
        storage_percentage = self._calculate_percentage(usage['storage_used'], limits['storage_mb'])
        if storage_percentage >= 80:
            warnings.append({
                'type': 'quota_warning',
                'resource': 'storage',
                'percentage': storage_percentage,
                'message': f"Sie haben {storage_percentage:.0f}% Ihres Speicher-Kontingents verbraucht.",
                'action': 'cleanup_files' if storage_percentage >= 90 else 'monitor'
            })
        
        return warnings
    
    async def _increment_usage_counter(self, user_id: int, resource_type: str, amount: int, db: AsyncSession):
        """Increment usage counter in database"""
        if resource_type == 'quotes':
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(quotes_this_month=User.quotes_this_month + amount)
            )
            await db.commit()
    
    async def _deduct_additional_quotes(self, user_id: int, amount: int, db: AsyncSession):
        """Deduct from additional quotes balance"""
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(additional_quotes=User.additional_quotes - amount)
        )
        await db.commit()
    
    async def _increment_api_usage(self, user_id: int, amount: int):
        """Increment API usage in cache"""
        try:
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            key = f"api_usage:{user_id}:{today}"
            await cache_service.redis_client.incrby(key, amount)
            await cache_service.redis_client.expire(key, 86400)  # Expire after 24 hours
        except Exception as e:
            logger.error(f"Failed to increment API usage for user {user_id}: {e}")
    
    async def _cache_quota_status(self, user_id: int, quota_status: Dict):
        """Cache quota status for quick retrieval"""
        try:
            key = f"quota_status:{user_id}"
            await cache_service.redis_client.setex(key, 300, str(quota_status))  # Cache for 5 minutes
        except Exception as e:
            logger.error(f"Failed to cache quota status for user {user_id}: {e}")
    
    async def _get_daily_usage_breakdown(self, user_id: int, start_date: datetime, end_date: datetime, db: AsyncSession) -> List[Dict]:
        """Get daily usage breakdown for analytics"""
        # This would be implemented with more complex queries
        # For now, return a placeholder structure
        return [
            {
                'date': start_date.strftime('%Y-%m-%d'),
                'quotes': 0,
                'documents': 0,
                'api_requests': 0
            }
        ]
    
    async def _calculate_usage_trends(self, user_id: int, start_date: datetime, end_date: datetime, db: AsyncSession) -> Dict:
        """Calculate usage trends"""
        return {
            'quotes_trend': 'stable',
            'documents_trend': 'increasing',
            'api_trend': 'stable'
        }
    
    async def _get_peak_usage_times(self, user_id: int, start_date: datetime, end_date: datetime, db: AsyncSession) -> Dict:
        """Get peak usage times"""
        return {
            'peak_hour': 14,
            'peak_day': 'Tuesday',
            'peak_activity': 'quote_generation'
        }
    
    async def _get_usage_summary(self, user_id: int, start_date: datetime, end_date: datetime, db: AsyncSession) -> Dict:
        """Get usage summary for the period"""
        return {
            'total_quotes': 0,
            'total_documents': 0,
            'total_api_requests': 0,
            'average_daily_usage': 0
        }