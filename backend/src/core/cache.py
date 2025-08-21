import redis.asyncio as redis
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import timedelta
from core.settings import settings

logger = logging.getLogger(__name__)

class CacheService:
    """Redis cache service for conversation and quote caching"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.enabled = False
        
    async def connect(self):
        """Initialize Redis connection"""
        try:
            # For development, use simple connection
            if settings.debug:
                self.redis_client = redis.Redis(
                    host='localhost',
                    port=6379,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            else:
                # Production Redis with password
                self.redis_client = redis.Redis(
                    host='redis',
                    port=6379,
                    password=settings.redis_password if hasattr(settings, 'redis_password') else None,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            
            # Test connection
            await self.redis_client.ping()
            self.enabled = True
            logger.info("Redis cache connection established")
            
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            self.enabled = False
            self.redis_client = None
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None
            self.enabled = False
    
    async def get_conversation_history(self, user_id: int, conversation_id: str = "default") -> List[Dict]:
        """Get cached conversation history"""
        if not self.enabled:
            return []
        
        try:
            key = f"conversation:{user_id}:{conversation_id}"
            cached_data = await self.redis_client.get(key)
            
            if cached_data:
                return json.loads(cached_data)
            return []
            
        except Exception as e:
            logger.error(f"Error getting conversation from cache: {e}")
            return []
    
    async def set_conversation_history(self, user_id: int, conversation_history: List[Dict], 
                                     conversation_id: str = "default", ttl: int = 3600):
        """Cache conversation history with TTL"""
        if not self.enabled:
            return
        
        try:
            key = f"conversation:{user_id}:{conversation_id}"
            await self.redis_client.setex(
                key, 
                ttl, 
                json.dumps(conversation_history, ensure_ascii=False)
            )
            logger.debug(f"Cached conversation for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error caching conversation: {e}")
    
    async def append_to_conversation(self, user_id: int, message: Dict, 
                                   conversation_id: str = "default", ttl: int = 3600):
        """Append message to conversation history"""
        if not self.enabled:
            return
        
        try:
            # Get existing conversation
            history = await self.get_conversation_history(user_id, conversation_id)
            
            # Append new message
            history.append(message)
            
            # Keep only last 20 messages to prevent memory issues
            if len(history) > 20:
                history = history[-20:]
            
            # Cache updated conversation
            await self.set_conversation_history(user_id, history, conversation_id, ttl)
            
        except Exception as e:
            logger.error(f"Error appending to conversation: {e}")
    
    async def clear_conversation(self, user_id: int, conversation_id: str = "default"):
        """Clear conversation history for user"""
        if not self.enabled:
            return
        
        try:
            key = f"conversation:{user_id}:{conversation_id}"
            await self.redis_client.delete(key)
            logger.debug(f"Cleared conversation for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error clearing conversation: {e}")
    
    async def cache_quote_analysis(self, analysis_id: str, analysis_data: Dict, ttl: int = 1800):
        """Cache AI analysis results for quote generation"""
        if not self.enabled:
            return
        
        try:
            key = f"quote_analysis:{analysis_id}"
            await self.redis_client.setex(
                key,
                ttl,
                json.dumps(analysis_data, ensure_ascii=False)
            )
            logger.debug(f"Cached quote analysis {analysis_id}")
            
        except Exception as e:
            logger.error(f"Error caching quote analysis: {e}")
    
    async def get_cached_quote_analysis(self, analysis_id: str) -> Optional[Dict]:
        """Get cached quote analysis"""
        if not self.enabled:
            return None
        
        try:
            key = f"quote_analysis:{analysis_id}"
            cached_data = await self.redis_client.get(key)
            
            if cached_data:
                return json.loads(cached_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached quote analysis: {e}")
            return None
    
    async def set_user_session(self, user_id: int, session_data: Dict, ttl: int = 7200):
        """Cache user session data"""
        if not self.enabled:
            return
        
        try:
            key = f"user_session:{user_id}"
            await self.redis_client.setex(
                key,
                ttl,
                json.dumps(session_data, ensure_ascii=False)
            )
            
        except Exception as e:
            logger.error(f"Error caching user session: {e}")
    
    async def get_user_session(self, user_id: int) -> Optional[Dict]:
        """Get cached user session data"""
        if not self.enabled:
            return None
        
        try:
            key = f"user_session:{user_id}"
            cached_data = await self.redis_client.get(key)
            
            if cached_data:
                return json.loads(cached_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting user session: {e}")
            return None
    
    async def increment_rate_limit(self, user_id: int, window_seconds: int = 900) -> int:
        """Increment rate limit counter and return current count"""
        if not self.enabled:
            return 0
        
        try:
            key = f"rate_limit:{user_id}"
            pipe = self.redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            results = await pipe.execute()
            return results[0]
            
        except Exception as e:
            logger.error(f"Error incrementing rate limit: {e}")
            return 0
    
    async def get_rate_limit_count(self, user_id: int) -> int:
        """Get current rate limit count for user"""
        if not self.enabled:
            return 0
        
        try:
            key = f"rate_limit:{user_id}"
            count = await self.redis_client.get(key)
            return int(count) if count else 0
            
        except Exception as e:
            logger.error(f"Error getting rate limit count: {e}")
            return 0

# Global cache instance
cache_service = CacheService()