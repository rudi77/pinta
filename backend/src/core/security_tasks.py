import asyncio
import logging
from datetime import datetime, timedelta
from core.security import cleanup_expired_blacklist
from core.cache import cache_service

logger = logging.getLogger(__name__)

class SecurityTaskManager:
    """Manages periodic security tasks"""
    
    def __init__(self):
        self.running = False
        self.tasks = []
    
    async def start_background_tasks(self):
        """Start all security background tasks"""
        if self.running:
            return
        
        self.running = True
        logger.info("Starting security background tasks...")
        
        # Start cleanup tasks
        self.tasks = [
            asyncio.create_task(self._token_blacklist_cleanup_task()),
            asyncio.create_task(self._security_metrics_task()),
            asyncio.create_task(self._failed_login_cleanup_task())
        ]
        
        logger.info(f"Started {len(self.tasks)} security background tasks")
    
    async def stop_background_tasks(self):
        """Stop all security background tasks"""
        if not self.running:
            return
        
        self.running = False
        logger.info("Stopping security background tasks...")
        
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete cancellation
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        
        logger.info("Security background tasks stopped")
    
    async def _token_blacklist_cleanup_task(self):
        """Periodic cleanup of expired blacklisted tokens"""
        while self.running:
            try:
                await cleanup_expired_blacklist()
                
                # Run every hour
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in blacklist cleanup task: {e}")
                # Continue running even if one iteration fails
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def _security_metrics_task(self):
        """Collect and log security metrics"""
        while self.running:
            try:
                await self._collect_security_metrics()
                
                # Run every 30 minutes
                await asyncio.sleep(1800)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in security metrics task: {e}")
                await asyncio.sleep(60)
    
    async def _failed_login_cleanup_task(self):
        """Cleanup old failed login attempts"""
        while self.running:
            try:
                await self._cleanup_old_rate_limits()
                
                # Run every 2 hours
                await asyncio.sleep(7200)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in failed login cleanup task: {e}")
                await asyncio.sleep(60)
    
    async def _collect_security_metrics(self):
        """Collect security metrics for monitoring"""
        try:
            if not cache_service.enabled:
                return
            
            # Count blacklisted tokens
            blacklist_keys = await cache_service.redis_client.keys("blacklist:*")
            blacklist_count = len(blacklist_keys)
            
            # Count rate limited IPs
            rate_limit_keys = await cache_service.redis_client.keys("auth:*")
            rate_limited_ips = len(rate_limit_keys)
            
            # Count revoked users
            revoked_keys = await cache_service.redis_client.keys("user_revoked:*")
            revoked_users = len(revoked_keys)
            
            # Log metrics
            if blacklist_count > 0 or rate_limited_ips > 0 or revoked_users > 0:
                logger.info(
                    f"Security metrics - Blacklisted tokens: {blacklist_count}, "
                    f"Rate limited IPs: {rate_limited_ips}, "
                    f"Users with revoked tokens: {revoked_users}"
                )
            
            # Store metrics in cache for monitoring endpoints
            metrics = {
                "blacklisted_tokens": blacklist_count,
                "rate_limited_ips": rate_limited_ips,
                "revoked_users": revoked_users,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await cache_service.redis_client.setex(
                "security_metrics", 
                3600,  # 1 hour TTL
                str(metrics)
            )
            
        except Exception as e:
            logger.error(f"Error collecting security metrics: {e}")
    
    async def _cleanup_old_rate_limits(self):
        """Clean up expired rate limit entries"""
        try:
            if not cache_service.enabled:
                return
            
            # Get all rate limit keys
            pattern = "auth:*"
            keys = await cache_service.redis_client.keys(pattern)
            
            cleaned_count = 0
            for key in keys:
                ttl = await cache_service.redis_client.ttl(key)
                if ttl <= 0:  # Expired or no TTL
                    await cache_service.redis_client.delete(key)
                    cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired rate limit entries")
                
        except Exception as e:
            logger.error(f"Error cleaning up rate limits: {e}")
    
    async def get_security_status(self):
        """Get current security status"""
        try:
            if not cache_service.enabled:
                return {"status": "cache_disabled"}
            
            # Get cached metrics
            metrics_data = await cache_service.redis_client.get("security_metrics")
            
            status = {
                "running": self.running,
                "active_tasks": len([t for t in self.tasks if not t.done()]),
                "cache_enabled": cache_service.enabled
            }
            
            if metrics_data:
                import ast
                try:
                    metrics = ast.literal_eval(metrics_data)
                    status.update(metrics)
                except:
                    pass
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting security status: {e}")
            return {"status": "error", "error": str(e)}

# Global security task manager
security_task_manager = SecurityTaskManager()

# Helper function to start security tasks
async def start_security_tasks():
    """Start security background tasks"""
    await security_task_manager.start_background_tasks()

# Helper function to stop security tasks
async def stop_security_tasks():
    """Stop security background tasks"""
    await security_task_manager.stop_background_tasks()

# Helper function to get security status
async def get_security_status():
    """Get security status"""
    return await security_task_manager.get_security_status()