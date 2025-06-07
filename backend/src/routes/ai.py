from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime

from src.services.ai_service import AIService
from src.core.security import get_current_user
from src.models.models import User
from src.schemas.schemas import (
    AIAnalysisRequest, 
    AIAnalysisResponse,
    AIQuestionResponse,
    AIFollowUpRequest,
    AIQuoteGenerationRequest,
    AIQuoteGenerationResponse
)

router = APIRouter(tags=["AI"])
logger = logging.getLogger(__name__)

# Initialize AI service
ai_service = AIService()

@router.post("/analyze-input", response_model=AIAnalysisResponse)
async def analyze_project_input(
    request: AIAnalysisRequest,
    current_user: User = Depends(get_current_user)
):
    """Analyze project description and generate intelligent follow-up questions"""
    try:
        logger.info(f"Analyzing project input for user {current_user.id}")
        
        result = await ai_service.analyze_project_description(
            description=request.description,
            context=request.context or "initial_input"
        )
        
        return AIAnalysisResponse(
            analysis=result.get("analysis", {}),
            questions=result.get("questions", []),
            suggestions=result.get("suggestions", []),
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error analyzing project input: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to analyze project input")

@router.post("/ask-question", response_model=AIQuestionResponse)
async def ask_follow_up_question(
    request: AIFollowUpRequest,
    current_user: User = Depends(get_current_user)
):
    """Handle follow-up questions in the AI conversation"""
    try:
        logger.info(f"Processing follow-up question for user {current_user.id}")
        
        result = await ai_service.ask_follow_up_question(
            conversation_history=request.conversation_history,
            user_message=request.message
        )
        
        return AIQuestionResponse(
            response=result.get("response", ""),
            needs_more_info=result.get("needs_more_info", False),
            suggested_questions=result.get("suggested_questions", []),
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error processing follow-up question: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process question")

@router.post("/generate-quote", response_model=AIQuoteGenerationResponse)
async def generate_quote_with_ai(
    request: AIQuoteGenerationRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate a detailed quote based on project data and user answers"""
    try:
        logger.info(f"Generating AI quote for user {current_user.id}")
        
        result = await ai_service.process_answers_and_generate_quote(
            project_data=request.project_data,
            answers=request.answers
        )
        
        return AIQuoteGenerationResponse(
            quote=result.get("quote", {}),
            items=result.get("items", []),
            notes=result.get("notes", ""),
            recommendations=result.get("recommendations", []),
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error generating AI quote: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate quote")

@router.post("/upload-document")
async def upload_document_for_analysis(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload and analyze documents (PDFs, images) for project information"""
    try:
        logger.info(f"Processing document upload for user {current_user.id}")
        
        # Validate file type
        allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp']
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file type. Please upload PDF, JPEG, PNG, or WebP files."
            )
        
        # Read file content
        content = await file.read()
        
        # For now, return a mock response
        # In production, you would implement OCR and document analysis
        return {
            "success": True,
            "filename": file.filename,
            "size": len(content),
            "analysis": {
                "extracted_text": "Mock extracted text from document",
                "detected_rooms": ["Wohnzimmer", "Küche"],
                "estimated_area": 45,
                "notes": "Document analysis is currently in development"
            },
            "message": "Document uploaded successfully. Analysis feature coming soon."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing document upload: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process document")

@router.get("/conversation-history/{quote_id}")
async def get_conversation_history(
    quote_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get conversation history for a specific quote"""
    try:
        # For now, return mock conversation history
        # In production, you would fetch from database
        return {
            "quote_id": quote_id,
            "conversation": [
                {
                    "role": "assistant",
                    "content": "Hallo! Ich helfe Ihnen bei der Erstellung Ihres Kostenvoranschlags. Können Sie mir mehr über Ihr Projekt erzählen?",
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "role": "user", 
                    "content": "Ich möchte mein Wohnzimmer streichen lassen.",
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error fetching conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch conversation history")

@router.get("/ai-status")
async def get_ai_status():
    """Get current AI service status and capabilities"""
    return {
        "ai_enabled": ai_service.enabled,
        "model": ai_service.model if ai_service.enabled else None,
        "capabilities": {
            "project_analysis": True,
            "question_generation": True,
            "quote_generation": True,
            "document_analysis": False,  # Coming soon
            "conversation_memory": True
        },
        "status": "operational" if ai_service.enabled else "mock_mode"
    }

