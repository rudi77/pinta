import redis.asyncio as redis
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from src.core.settings import settings

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
                                   conversation_id: str = "default", ttl: int = 7200):
        """Append message to conversation history with optimized performance"""
        if not self.enabled:
            return
        
        try:
            # Get existing conversation
            history = await self.get_conversation_history(user_id, conversation_id)
            
            # Append new message with timestamp
            message_with_timestamp = {
                **message,
                "timestamp": message.get("timestamp", json.dumps(datetime.now(), default=str))
            }
            history.append(message_with_timestamp)
            
            # Keep only last 30 messages for better context (increased from 20)
            if len(history) > 30:
                history = history[-30:]
            
            # Cache updated conversation with longer TTL (2 hours)
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
    
    # === PERFORMANCE ENHANCEMENTS FOR CHAT ===
    
    async def cache_streaming_session(self, user_id: int, session_id: str, 
                                    data: Dict, ttl: int = 600):
        """Cache streaming session data for real-time updates"""
        if not self.enabled:
            return
        
        try:
            key = f"stream_session:{user_id}:{session_id}"
            await self.redis_client.setex(
                key,
                ttl,
                json.dumps(data, ensure_ascii=False)
            )
            logger.debug(f"Cached streaming session {session_id}")
            
        except Exception as e:
            logger.error(f"Error caching streaming session: {e}")
    
    async def get_streaming_session(self, user_id: int, session_id: str) -> Optional[Dict]:
        """Get streaming session data"""
        if not self.enabled:
            return None
        
        try:
            key = f"stream_session:{user_id}:{session_id}"
            cached_data = await self.redis_client.get(key)
            
            if cached_data:
                return json.loads(cached_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting streaming session: {e}")
            return None
    
    async def cache_ai_context(self, user_id: int, context_data: Dict, ttl: int = 1800):
        """Cache AI context for faster response generation"""
        if not self.enabled:
            return
        
        try:
            key = f"ai_context:{user_id}"
            await self.redis_client.setex(
                key,
                ttl,
                json.dumps(context_data, ensure_ascii=False)
            )
            logger.debug(f"Cached AI context for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error caching AI context: {e}")
    
    async def get_ai_context(self, user_id: int) -> Optional[Dict]:
        """Get cached AI context"""
        if not self.enabled:
            return None
        
        try:
            key = f"ai_context:{user_id}"
            cached_data = await self.redis_client.get(key)
            
            if cached_data:
                return json.loads(cached_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting AI context: {e}")
            return None
    
    async def track_response_time(self, user_id: int, response_time_ms: float):
        """Track response times for performance monitoring"""
        if not self.enabled:
            return
        
        try:
            key = f"response_times:{user_id}"
            # Store as sorted set with timestamp as score
            timestamp = datetime.now().timestamp()
            await self.redis_client.zadd(key, {str(response_time_ms): timestamp})
            
            # Keep only last 100 response times
            await self.redis_client.zremrangebyrank(key, 0, -101)
            await self.redis_client.expire(key, 3600)  # Expire after 1 hour
            
        except Exception as e:
            logger.error(f"Error tracking response time: {e}")
    
    async def get_average_response_time(self, user_id: int) -> float:
        """Get average response time for user"""
        if not self.enabled:
            return 0.0
        
        try:
            key = f"response_times:{user_id}"
            times = await self.redis_client.zrange(key, 0, -1)
            
            if times:
                total = sum(float(time) for time in times)
                return total / len(times)
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting average response time: {e}")
            return 0.0

# Global cache instance
cache_service = CacheService()