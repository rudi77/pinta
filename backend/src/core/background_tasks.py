import asyncio
import logging
import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import AsyncSessionLocal
from core.cache import cache_service
from services.ai_service import AIService
from models.models import Quote, QuoteItem, User, Document

logger = logging.getLogger(__name__)

class BackgroundTaskManager:
    """Manages background tasks for quote generation and processing"""
    
    def __init__(self):
        self.ai_service = AIService()
        self.running_tasks: Dict[str, asyncio.Task] = {}
    
    async def generate_quote_async(self, 
                                  task_id: str,
                                  user_id: int,
                                  project_data: Dict,
                                  answers: List[Dict],
                                  conversation_history: Optional[List[Dict]] = None,
                                  document_files: Optional[List[Dict]] = None) -> Dict:
        """Generate quote in background task"""
        
        try:
            start_time = datetime.now()
            logger.info(f"Starting background quote generation task {task_id} for user {user_id}")
            
            # Update task status to processing with ETA
            await self._update_task_status(task_id, "processing", {
                "progress": 10, 
                "message": "Initialisierung...",
                "estimated_completion": 45  # seconds
            })
            
            # Cache task progress for WebSocket updates
            await cache_service.cache_streaming_session(user_id, task_id, {
                "type": "quote_generation",
                "status": "processing",
                "progress": 10,
                "start_time": start_time.isoformat()
            })
            
            # Step 1: AI Analysis with performance tracking
            logger.debug(f"Task {task_id}: Starting AI analysis")
            ai_start_time = datetime.now()
            
            quote_result = await self.ai_service.process_answers_and_generate_quote(
                project_data=project_data,
                answers=answers,
                conversation_history=conversation_history,
                document_files=document_files
            )
            
            ai_duration = (datetime.now() - ai_start_time).total_seconds() * 1000
            await cache_service.track_response_time(user_id, ai_duration)
            
            await self._update_task_status(task_id, "processing", {
                "progress": 50,
                "message": "KI-Analyse abgeschlossen, speichere Angebot...",
                "ai_processing_time": ai_duration
            })
            
            # Step 2: Save to Database (70% progress)
            logger.debug(f"Task {task_id}: Saving quote to database")
            async with AsyncSessionLocal() as db:
                # Get user
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                
                if not user:
                    raise ValueError(f"User {user_id} not found")
                
                # Create quote
                quote_number = f"Q-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
                
                quote = Quote(
                    quote_number=quote_number,
                    user_id=user_id,
                    customer_name=project_data.get('customer_name', 'Unbekannter Kunde'),
                    customer_email=project_data.get('customer_email'),
                    customer_phone=project_data.get('customer_phone'),
                    customer_address=project_data.get('customer_address'),
                    project_title=quote_result['quote']['project_title'],
                    project_description=project_data.get('description', ''),
                    total_amount=quote_result['quote']['total_amount'],
                    labor_hours=quote_result['quote']['labor_hours'],
                    hourly_rate=quote_result['quote']['hourly_rate'],
                    material_cost=quote_result['quote']['material_cost'],
                    additional_costs=quote_result['quote']['additional_costs'],
                    status='completed',
                    ai_processing_status='completed',
                    created_by_ai=True,
                    conversation_history=json.dumps(conversation_history) if conversation_history else None
                )
                
                db.add(quote)
                await db.flush()  # Get the quote ID
                
                await self._update_task_status(task_id, "processing", {"progress": 80})
                
                # Step 3: Save quote items
                for item_data in quote_result.get('items', []):
                    quote_item = QuoteItem(
                        quote_id=quote.id,
                        description=item_data['description'],
                        quantity=item_data['quantity'],
                        unit=item_data['unit'],
                        unit_price=item_data['unit_price'],
                        total_price=item_data['total_price'],
                        category=item_data['category']
                    )
                    db.add(quote_item)
                
                await db.commit()
                
                await self._update_task_status(task_id, "processing", {"progress": 90})
                
                # Step 4: Update user quota
                if not user.is_premium:
                    user.quotes_this_month = (user.quotes_this_month or 0) + 1
                    await db.commit()
            
            # Step 5: Cache result and complete
            result = {
                "quote_id": quote.id,
                "quote_number": quote.quote_number,
                "quote_result": quote_result,
                "status": "completed"
            }
            
            await self._update_task_status(task_id, "completed", {
                "progress": 100,
                "result": result
            })
            
            logger.info(f"Background quote generation task {task_id} completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Background quote generation task {task_id} failed: {str(e)}")
            await self._update_task_status(task_id, "failed", {
                "error": str(e),
                "progress": 0
            })
            raise
        
        finally:
            # Remove from running tasks
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
    
    async def _update_task_status(self, task_id: str, status: str, data: Dict):
        """Update task status in cache"""
        task_data = {
            "status": status,
            "updated_at": datetime.now().isoformat(),
            **data
        }
        
        # Cache for 1 hour
        await cache_service.cache_quote_analysis(f"task:{task_id}", task_data, ttl=3600)
    
    async def start_quote_generation_task(self, 
                                        user_id: int,
                                        project_data: Dict,
                                        answers: List[Dict],
                                        conversation_history: Optional[List[Dict]] = None,
                                        document_files: Optional[List[Dict]] = None) -> str:
        """Start a background quote generation task"""
        
        task_id = f"quote-gen-{uuid.uuid4()}"
        
        # Initialize task status
        await self._update_task_status(task_id, "queued", {"progress": 0})
        
        # Start the background task
        task = asyncio.create_task(
            self.generate_quote_async(
                task_id=task_id,
                user_id=user_id,
                project_data=project_data,
                answers=answers,
                conversation_history=conversation_history,
                document_files=document_files
            )
        )
        
        self.running_tasks[task_id] = task
        
        logger.info(f"Started background quote generation task {task_id} for user {user_id}")
        return task_id
    
    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get current status of a background task"""
        cached_status = await cache_service.get_cached_quote_analysis(f"task:{task_id}")
        return cached_status
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running background task"""
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            task.cancel()
            del self.running_tasks[task_id]
            
            await self._update_task_status(task_id, "cancelled", {"progress": 0})
            return True
        
        return False
    
    async def cleanup_completed_tasks(self):
        """Clean up completed or failed tasks"""
        completed_tasks = []
        
        for task_id, task in self.running_tasks.items():
            if task.done():
                completed_tasks.append(task_id)
        
        for task_id in completed_tasks:
            del self.running_tasks[task_id]
            logger.debug(f"Cleaned up completed task {task_id}")
    
    async def get_running_tasks_count(self) -> int:
        """Get count of currently running tasks"""
        await self.cleanup_completed_tasks()
        return len(self.running_tasks)

# Global background task manager
background_task_manager = BackgroundTaskManager()