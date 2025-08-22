from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

from core.database import get_db
from core.cache import cache_service
from core.websocket_manager import websocket_manager
from core.background_tasks import background_task_manager
from core.security import get_current_user
from services.ai_service import AIService
from models.models import User
from core.settings import settings
from schemas.schemas import IntelligentFollowUpRequest, IntelligentFollowUpResponse

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
logger = logging.getLogger(__name__)

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """WebSocket endpoint for real-time chat communication"""
    
    await websocket_manager.connect(websocket, user_id, "chat")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            message_type = message_data.get("type")
            
            if message_type == "chat_message":
                await handle_chat_message(websocket, user_id, message_data)
            elif message_type == "get_task_status":
                await handle_task_status_request(websocket, user_id, message_data)
            elif message_type == "cancel_task":
                await handle_task_cancellation(websocket, user_id, message_data)
            elif message_type == "ping":
                await websocket_manager.send_personal_message({
                    "type": "pong",
                    "timestamp": message_data.get("timestamp")
                }, websocket)
            else:
                await websocket_manager.send_personal_message({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                }, websocket)
                
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {str(e)}")
        websocket_manager.disconnect(websocket)

async def handle_chat_message(websocket: WebSocket, user_id: int, message_data: Dict):
    """Handle incoming chat message with streaming response"""
    
    try:
        user_message = message_data.get("message", "")
        conversation_id = message_data.get("conversation_id", "default")
        
        if not user_message.strip():
            await websocket_manager.send_personal_message({
                "type": "error",
                "message": "Empty message received"
            }, websocket)
            return
        
        # Check rate limiting
        rate_count = await cache_service.increment_rate_limit(
            user_id, 
            settings.rate_limit_window_minutes * 60
        )
        
        if rate_count > settings.rate_limit_requests:
            await websocket_manager.send_personal_message({
                "type": "rate_limit_exceeded",
                "message": f"Rate limit exceeded. Max {settings.rate_limit_requests} requests per {settings.rate_limit_window_minutes} minutes.",
                "retry_after": settings.rate_limit_window_minutes * 60
            }, websocket)
            return
        
        # Get conversation history from cache
        conversation_history = await cache_service.get_conversation_history(user_id, conversation_id)
        
        # Add user message to conversation
        user_msg = {
            "role": "user",
            "content": user_message,
            "timestamp": message_data.get("timestamp")
        }
        
        await cache_service.append_to_conversation(user_id, user_msg, conversation_id)
        
        # Initialize AI service
        ai_service = AIService()
        
        # Start streaming response with intelligent follow-up
        await websocket_manager.send_streaming_response(
            user_id=user_id,
            stream_generator=ai_service.ask_follow_up_question_stream(
                conversation_history + [user_msg],
                user_message
            ),
            task_id=f"chat-{conversation_id}"
        )
        
        # Note: We don't store the AI response in conversation here
        # as it will be streamed. The frontend should handle adding
        # the complete response to conversation when streaming ends.
        
    except Exception as e:
        logger.error(f"Error handling chat message: {str(e)}")
        await websocket_manager.send_personal_message({
            "type": "error",
            "message": "Error processing chat message"
        }, websocket)

async def handle_task_status_request(websocket: WebSocket, user_id: int, message_data: Dict):
    """Handle task status request"""
    
    task_id = message_data.get("task_id")
    if not task_id:
        await websocket_manager.send_personal_message({
            "type": "error",
            "message": "Task ID required"
        }, websocket)
        return
    
    task_status = await background_task_manager.get_task_status(task_id)
    
    await websocket_manager.send_personal_message({
        "type": "task_status_response",
        "task_id": task_id,
        "status": task_status
    }, websocket)

async def handle_task_cancellation(websocket: WebSocket, user_id: int, message_data: Dict):
    """Handle task cancellation request"""
    
    task_id = message_data.get("task_id")
    if not task_id:
        await websocket_manager.send_personal_message({
            "type": "error",
            "message": "Task ID required"
        }, websocket)
        return
    
    cancelled = await background_task_manager.cancel_task(task_id)
    
    await websocket_manager.send_personal_message({
        "type": "task_cancelled" if cancelled else "task_cancel_failed",
        "task_id": task_id,
        "message": "Task cancelled successfully" if cancelled else "Task not found or already completed"
    }, websocket)

@router.post("/analyze-project")
async def analyze_project_description(
    request: Dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Analyze project description and return intelligent questions"""
    
    try:
        start_time = datetime.now()
        description = request.get("description", "")
        context = request.get("context", "initial_input")
        conversation_id = request.get("conversation_id", "default")
        
        if not description.strip():
            raise HTTPException(status_code=400, detail="Project description is required")
        
        # Check rate limiting with better error message
        rate_count = await cache_service.increment_rate_limit(
            current_user.id,
            settings.rate_limit_window_minutes * 60
        )
        
        if rate_count > settings.rate_limit_requests:
            retry_after = settings.rate_limit_window_minutes * 60
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {settings.rate_limit_requests} requests per {settings.rate_limit_window_minutes} minutes.",
                headers={"Retry-After": str(retry_after)}
            )
        
        # Get conversation history from cache
        conversation_history = await cache_service.get_conversation_history(
            current_user.id, 
            conversation_id
        )
        
        # Check for cached AI context to speed up response
        ai_context = await cache_service.get_ai_context(current_user.id)
        
        # Initialize AI service
        ai_service = AIService()
        
        # Analyze project with context
        analysis_result = await ai_service.analyze_project_description(
            description=description,
            context=context,
            conversation_history=conversation_history
        )
        
        # Track performance
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        await cache_service.track_response_time(current_user.id, processing_time)
        
        # Cache the user input and AI context
        user_message = {
            "role": "user",
            "content": description,
            "context": context,
            "timestamp": request.get("timestamp", datetime.now().isoformat())
        }
        
        await cache_service.append_to_conversation(
            current_user.id,
            user_message,
            conversation_id
        )
        
        # Cache AI context for future requests
        await cache_service.cache_ai_context(current_user.id, {
            "last_analysis": analysis_result,
            "project_context": description,
            "conversation_id": conversation_id
        })
        
        return {
            "success": True,
            "analysis": analysis_result,
            "conversation_id": conversation_id,
            "processing_time_ms": processing_time,
            "cached_context": ai_context is not None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in project analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/intelligent-followup", response_model=IntelligentFollowUpResponse)
async def get_intelligent_followup(
    request: IntelligentFollowUpRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate intelligent context-aware follow-up questions"""
    
    try:
        user_message = request.message
        conversation_id = request.conversation_id
        additional_context = request.context or {}
        
        if not user_message.strip():
            raise HTTPException(status_code=400, detail="User message is required")
        
        # Check rate limiting
        rate_count = await cache_service.increment_rate_limit(
            current_user.id,
            settings.rate_limit_window_minutes * 60
        )
        
        if rate_count > settings.rate_limit_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {settings.rate_limit_requests} requests per {settings.rate_limit_window_minutes} minutes."
            )
        
        # Get conversation history
        conversation_history = await cache_service.get_conversation_history(
            current_user.id, 
            conversation_id
        )
        
        # Initialize AI service
        ai_service = AIService()
        
        # Generate intelligent follow-up questions
        followup_result = await ai_service.ask_intelligent_follow_up(
            conversation_history=conversation_history,
            user_message=user_message,
            context=additional_context
        )
        
        # Cache the user message
        await cache_service.append_to_conversation(
            current_user.id,
            {
                "role": "user",
                "content": user_message,
                "timestamp": request.get("timestamp")
            },
            conversation_id
        )
        
        # Cache the AI response
        await cache_service.append_to_conversation(
            current_user.id,
            {
                "role": "assistant",
                "content": followup_result.get("response", ""),
                "questions": followup_result.get("questions", []),
                "completion_status": followup_result.get("completion_status", {}),
                "timestamp": datetime.now().isoformat()
            },
            conversation_id
        )
        
        return {
            "success": True,
            "followup": followup_result,
            "conversation_id": conversation_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in intelligent follow-up: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/generate-quote")
async def generate_quote(
    request: Dict,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate quote based on project data and answers (background task)"""
    
    try:
        project_data = request.get("project_data", {})
        answers = request.get("answers", [])
        conversation_id = request.get("conversation_id", "default")
        document_files = request.get("document_files", [])
        
        if not project_data or not answers:
            raise HTTPException(status_code=400, detail="Project data and answers are required")
        
        # Check user quota
        if not current_user.is_premium:
            total_available = 3 + (current_user.additional_quotes or 0)
            if (current_user.quotes_this_month or 0) >= total_available:
                raise HTTPException(
                    status_code=402,
                    detail="Quote limit reached. Upgrade to premium for unlimited quotes."
                )
        
        # Get conversation history
        conversation_history = await cache_service.get_conversation_history(
            current_user.id,
            conversation_id
        )
        
        # Start background task
        task_id = await background_task_manager.start_quote_generation_task(
            user_id=current_user.id,
            project_data=project_data,
            answers=answers,
            conversation_history=conversation_history,
            document_files=document_files
        )
        
        # Send immediate response with task ID
        return {
            "success": True,
            "message": "Quote generation started",
            "task_id": task_id,
            "estimated_completion": "30-60 seconds"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting quote generation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/task-status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get status of a background task"""
    
    try:
        task_status = await background_task_manager.get_task_status(task_id)
        
        if not task_status:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {
            "success": True,
            "task_id": task_id,
            "status": task_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/conversation-history")
async def get_conversation_history(
    conversation_id: str = "default",
    current_user: User = Depends(get_current_user)
):
    """Get cached conversation history for user"""
    
    try:
        history = await cache_service.get_conversation_history(
            current_user.id,
            conversation_id
        )
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "history": history
        }
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/conversation-history")
async def clear_conversation_history(
    conversation_id: str = "default",
    current_user: User = Depends(get_current_user)
):
    """Clear conversation history for user"""
    
    try:
        await cache_service.clear_conversation(current_user.id, conversation_id)
        
        return {
            "success": True,
            "message": "Conversation history cleared",
            "conversation_id": conversation_id
        }
        
    except Exception as e:
        logger.error(f"Error clearing conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/stream-analysis")
async def stream_project_analysis(
    request: Dict,
    current_user: User = Depends(get_current_user)
):
    """Stream project analysis in real-time (Server-Sent Events alternative)"""
    
    try:
        description = request.get("description", "")
        context = request.get("context", "initial_input") 
        conversation_id = request.get("conversation_id", "default")
        
        if not description.strip():
            raise HTTPException(status_code=400, detail="Project description is required")
        
        # Rate limiting check
        rate_count = await cache_service.get_rate_limit_count(current_user.id)
        if rate_count > settings.rate_limit_requests:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        # Get conversation history
        conversation_history = await cache_service.get_conversation_history(
            current_user.id, 
            conversation_id
        )
        
        # Initialize AI service
        ai_service = AIService()
        
        # Create streaming generator
        async def generate_stream():
            try:
                # Stream the analysis
                async for chunk in ai_service.analyze_project_stream(
                    description=description,
                    context=context,
                    conversation_history=conversation_history
                ):
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                
                # Cache the conversation after completion
                await cache_service.append_to_conversation(
                    current_user.id,
                    {
                        "role": "user",
                        "content": description,
                        "context": context,
                        "timestamp": datetime.now().isoformat()
                    },
                    conversation_id
                )
                
            except Exception as e:
                error_chunk = {
                    "type": "error",
                    "error": str(e)
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in streaming analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/performance-stats")
async def get_performance_stats(
    current_user: User = Depends(get_current_user)
):
    """Get performance statistics for current user"""
    
    try:
        avg_response_time = await cache_service.get_average_response_time(current_user.id)
        rate_limit_count = await cache_service.get_rate_limit_count(current_user.id)
        
        return {
            "success": True,
            "stats": {
                "average_response_time_ms": avg_response_time,
                "current_rate_limit_count": rate_limit_count,
                "rate_limit_max": settings.rate_limit_requests,
                "rate_limit_window_minutes": settings.rate_limit_window_minutes
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting performance stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")