from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks
from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from src.services.ai_service import AIService
from src.services.pdf_service import PDFService
from src.core.security import get_current_user
from src.models.models import User, Quote, QuoteItem, Document as DocumentModel
from src.schemas.schemas import (
    AIAnalysisRequest, 
    AIAnalysisResponse,
    AIQuestionResponse,
    AIFollowUpRequest,
    AIQuoteGenerationRequest,
    AIQuoteGenerationResponse,
    AIConversationHistory,
    DocumentResponse,
    Document,
    ErrorResponse
)
from src.database import get_db

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
        
        # Initialize conversation history if not exists
        if not request.conversation_history:
            request.conversation_history = []
            
        # Add user's initial input to conversation
        request.conversation_history.append({
            "role": "user",
            "content": request.input,
            "timestamp": datetime.now().isoformat()
        })
        
        result = await ai_service.analyze_project_description(
            description=request.input,
            context=getattr(request, 'context', None) or "initial_input",
            conversation_history=request.conversation_history
        )
        
        # Add AI's response to conversation
        request.conversation_history.append({
            "role": "assistant",
            "content": json.dumps(result),
            "timestamp": datetime.now().isoformat()
        })
        
        print(result)

        return AIAnalysisResponse(
            analysis=result.get("analysis", {}),
            questions=result.get("questions", []),
            suggestions=result.get("suggestions", []),
            conversation_history=request.conversation_history,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error analyzing project input: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ask-question", response_model=AIQuestionResponse)
async def ask_follow_up_question(
    request: AIFollowUpRequest,
    current_user: User = Depends(get_current_user)
):
    """Handle follow-up questions in the AI conversation"""
    try:
        logger.info(f"Processing follow-up question for user {current_user.id}")
        
        # Add user's question to conversation
        request.conversation_history.append({
            "role": "user",
            "content": request.question,
            "timestamp": datetime.now().isoformat()
        })
        
        # conversation_history in dicts umwandeln
        history = [msg.model_dump() if hasattr(msg, 'model_dump') else dict(msg) for msg in request.conversation_history]
        
        result = await ai_service.ask_follow_up_question(
            conversation_history=history,
            user_message=request.question
        )
        
        # Add AI's response to conversation
        request.conversation_history.append({
            "role": "assistant",
            "content": result.get("response", ""),
            "timestamp": datetime.now().isoformat()
        })
        
        return AIQuestionResponse(
            response=result.get("response", ""),
            needs_more_info=result.get("needs_more_info", False),
            suggested_questions=result.get("suggested_questions", []),
            conversation_history=request.conversation_history,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error processing follow-up question: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-quote", response_model=AIQuoteGenerationResponse)
async def generate_quote_with_ai(
    request: AIQuoteGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate a detailed quote based on project data and user answers"""
    try:
        logger.info(f"Generating AI quote for user {current_user.id}")
        
        result = await ai_service.process_answers_and_generate_quote(
            project_data=request.project_data,
            answers=request.answers,
            conversation_history=request.conversation_history
        )
        
        # Create quote in database
        quote_number = generate_quote_number()
        
        # Convert conversation history to JSON string
        conversation_history = None
        if request.conversation_history:
            conversation_history = json.dumps([msg.model_dump() for msg in request.conversation_history])
        
        # Create quote
        quote = Quote(
            quote_number=quote_number,
            user_id=current_user.id,
            customer_name=result["quote"]["customer_name"],
            customer_email=result["quote"].get("customer_email"),
            customer_phone=result["quote"].get("customer_phone"),
            customer_address=result["quote"].get("customer_address"),
            project_title=result["quote"]["project_title"],
            project_description=result["quote"].get("project_description"),
            status="draft",
            ai_processing_status="completed",
            created_by_ai=True,
            conversation_history=conversation_history
        )
        
        db.add(quote)
        await db.flush()
        
        # Add quote items
        total_amount = 0.0
        for item in result["items"]:
            quote_item = QuoteItem(
                quote_id=quote.id,
                position=item["position"],
                description=item["description"],
                quantity=item["quantity"],
                unit=item["unit"],
                unit_price=item["unit_price"],
                total_price=item["total_price"],
                room_name=item.get("room_name"),
                area_sqm=item.get("area_sqm"),
                work_type=item.get("work_type")
            )
            db.add(quote_item)
            total_amount += item["total_price"]
        
        # Update quote with total amount
        quote.total_amount = total_amount
        
        await db.commit()
        
        # Generate PDF
        pdf_service = PDFService()
        pdf_result = pdf_service.generate_quote_pdf({
            "quote_number": quote.quote_number,
            "customer_name": quote.customer_name,
            "customer_email": quote.customer_email,
            "customer_phone": quote.customer_phone,
            "customer_address": quote.customer_address,
            "project_title": quote.project_title,
            "project_description": quote.project_description,
            "quote_items": [
                {
                    "position": item.position,
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                    "room_name": item.room_name
                }
                for item in quote.quote_items
            ]
        })
        
        # Add final quote generation to conversation
        if request.conversation_history:
            request.conversation_history.append({
                "role": "assistant",
                "content": "Kostenvoranschlag wurde erstellt und als PDF gespeichert",
                "timestamp": datetime.now().isoformat()
            })
        
        return AIQuoteGenerationResponse(
            quote=result.get("quote", {}),
            items=result.get("items", []),
            notes=result.get("notes", ""),
            recommendations=result.get("recommendations", []),
            conversation_history=request.conversation_history,
            success=True,
            pdf_url=pdf_result.get("pdf_url") if pdf_result.get("success") else None
        )
        
    except Exception as e:
        logger.error(f"Error generating AI quote: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-document", response_model=DocumentResponse)
async def upload_document_for_analysis(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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
        
        # Create upload directory if it doesn't exist
        upload_dir = os.path.join("uploads", str(current_user.id))
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(upload_dir, safe_filename)
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Create document record
        document = Document(
            user_id=current_user.id,
            filename=safe_filename,
            original_filename=file.filename,
            file_path=file_path,
            file_size=len(content),
            mime_type=file.content_type,
            processing_status="processing"
        )
        
        db.add(document)
        await db.commit()
        await db.refresh(document)
        
        # Analyze document in background
        try:
            analysis_result = await ai_service.analyze_document(
                file_content=content,
                filename=file.filename,
                content_type=file.content_type
            )
            
            # Update document with analysis results
            document.extracted_text = analysis_result.get("extracted_text")
            document.analysis_result = json.dumps(analysis_result)
            document.processing_status = "completed"
            
            await db.commit()
            await db.refresh(document)
            
        except Exception as e:
            logger.error(f"Error analyzing document: {str(e)}")
            document.processing_status = "failed"
            await db.commit()
            await db.refresh(document)
        
        return document
        
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
        raise HTTPException(status_code=500, detail=str(e))

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
            "document_analysis": True,  # Now enabled
            "conversation_memory": True
        },
        "status": "operational" if ai_service.enabled else "mock_mode"
    }

@router.get("/document-status/{document_id}", response_model=DocumentResponse)
async def get_document_status(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the status and analysis results of an uploaded document"""
    try:
        # Get document
        result = await db.execute(
            select(Document)
            .where(Document.id == document_id)
            .where(Document.user_id == current_user.id)
        )
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found"
            )
        
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get document status")

