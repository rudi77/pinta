from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks, Form
from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import asyncio
import base64

from src.services.ai_service import AIService
from src.services.rag_service import RagService
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
    ErrorResponse,
    QuickQuoteRequest,
    QuickQuoteResponse,
    QuickQuoteItemResponse,
    VisualEstimateResponse
)
from src.core.database import get_db
from src.core.settings import settings
from .quotes import generate_quote_number

router = APIRouter(prefix="/api/v1/ai", tags=["AI"])
logger = logging.getLogger(__name__)

# Initialize AI service
ai_service = AIService()
rag_service = RagService(ai_service=ai_service)


def _resolve_cost_params(request, current_user) -> dict:
    """Resolve cost parameters with priority: request > user profile > AI defaults (None)."""
    return {
        "hourly_rate": request.hourly_rate if request.hourly_rate is not None else current_user.hourly_rate,
        "material_cost_markup": request.material_cost_markup if request.material_cost_markup is not None else current_user.material_cost_markup,
    }

def default_json(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def _agent_pdf_url(pdf_path: Optional[str]) -> Optional[str]:
    """Map an absolute PDF path from the agent to the auth-gated download URL.

    The agent writes to ``backend/.taskforce_maler/quotes/<filename>``;
    the public download endpoint is ``/api/v1/agent/pdf/<filename>``.
    """
    if not pdf_path:
        return None
    return f"/api/v1/agent/pdf/{os.path.basename(pdf_path)}"

@router.post("/analyze-project", response_model=AIAnalysisResponse)
async def analyze_project_input(
    request: AIAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """First chat turn — backed by the unified Maler-Agent.

    The agent's free-form German reply (typically a clarifying question on
    the very first turn) is wrapped into ``questions[0].question`` because
    that's the field the React ChatQuoteWizard renders as the assistant
    bubble. Frontend stays unchanged.
    """
    try:
        logger.info(f"analyze-project (agent) user={current_user.id}")

        from src.agents.tools.save_quote_to_db import (
            current_conversation_id,
            current_user_id,
        )
        from src.services.agent_service import agent_service

        if not request.conversation_history:
            request.conversation_history = []

        user_token = current_user_id.set(current_user.id)
        conv_token = current_conversation_id.set(None)
        try:
            result = await agent_service.chat(
                db, current_user, request.input, channel="web",
            )
            current_conversation_id.set(result["conversation_id"])
        finally:
            current_user_id.reset(user_token)
            current_conversation_id.reset(conv_token)

        agent_text = (result.get("final_message") or "").strip() or (
            "Erzähl mir mehr über das Projekt — Räume, Flächen, Material."
        )

        request.conversation_history.append({
            "role": "user",
            "content": request.input,
            "timestamp": datetime.now().isoformat(),
        })
        request.conversation_history.append({
            "role": "assistant",
            "content": agent_text,
            "timestamp": datetime.now().isoformat(),
        })

        pdf_url = _agent_pdf_url(result.get("pdf_path"))
        return AIAnalysisResponse(
            analysis={
                "project_type": "agent",
                "estimated_area": None,
                "complexity": "medium",
                "missing_info": [],
                "conversation_id": result["conversation_id"],
            },
            questions=[{
                "id": "agent_reply",
                "question": agent_text,
                "type": "text",
            }],
            suggestions=[],
            conversation_history=request.conversation_history,
            quote_id=result.get("quote_id"),
            quote_number=result.get("quote_number"),
            pdf_url=pdf_url,
        )

    except Exception as e:
        logger.error(f"analyze-project (agent) failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

ALLOWED_VISUAL_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic"}
MAX_VISUAL_FILE_SIZE = 12 * 1024 * 1024  # 12 MB — Vision payloads degrade beyond this


@router.post("/visual-estimate", response_model=VisualEstimateResponse)
async def visual_estimate(
    file: UploadFile = File(...),
    extra_context: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Phase 1: Analyze a single on-site photo and return a structured estimate.

    This is a Premium-gated endpoint — the whole conversion hypothesis is that
    a contractor standing on a building site can snap one photo and get an
    instant, grounded estimate. That wow-effect is the Free→Premium trigger.
    """
    if not settings.vision_estimate_enabled:
        raise HTTPException(status_code=503, detail="Visual estimate feature is disabled.")

    if not current_user.is_premium:
        raise HTTPException(
            status_code=402,
            detail="Visual-Estimate ist ein Premium-Feature. Bitte upgraden Sie Ihren Account.",
        )

    if file.content_type not in ALLOWED_VISUAL_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Nicht unterstützter Bildtyp: {file.content_type}. Erlaubt: JPEG/PNG/WebP/HEIC.",
        )

    content = await file.read()
    if len(content) > MAX_VISUAL_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Bild ist zu groß (max. 12 MB).")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Leere Datei erhalten.")

    image_b64 = base64.b64encode(content).decode("utf-8")
    logger.info("Visual estimate requested by user %s (%d bytes)", current_user.id, len(content))

    result = await ai_service.visual_estimate(
        image_b64=image_b64,
        mime_type=file.content_type,
        extra_context=extra_context,
    )
    return VisualEstimateResponse(**result)


@router.post("/quote-suggestions")
async def quote_suggestions(
    request: dict,
    current_user: User = Depends(get_current_user)
):
    return {"suggested_materials": [], "labor_breakdown": {}, "alternative_options": []}

async def _run_agent_for_quote(
    user: User, db: AsyncSession, mission_text: str, *, channel: str = "web",
) -> dict:
    """Common entry point for the legacy AI routes — runs the unified agent
    and returns the freshly persisted Quote+items as plain dicts.

    The agent's save_quote_to_db tool writes the Quote/QuoteItem rows for
    us; here we just reload the latest one for this user and shape it into
    the legacy response schema.
    """
    from src.agents.tools.save_quote_to_db import (
        current_conversation_id,
        current_user_id,
    )
    from src.services.agent_service import agent_service

    user_token = current_user_id.set(user.id)
    conv_token = current_conversation_id.set(None)
    try:
        result = await agent_service.chat(
            db, user, mission_text, channel=channel,
        )
        current_conversation_id.set(result["conversation_id"])
    finally:
        current_user_id.reset(user_token)
        current_conversation_id.reset(conv_token)

    quote_id = result.get("quote_id")
    if quote_id is not None:
        latest_q = await db.get(Quote, quote_id)
        if latest_q is not None and latest_q.user_id != user.id:
            latest_q = None
    else:
        # Fallback for older tool results that did not return quote_id.
        latest_q = (await db.execute(
            select(Quote)
            .where(Quote.user_id == user.id)
            .order_by(Quote.id.desc())
            .limit(1)
        )).scalar_one_or_none()

    items_rows: list[QuoteItem] = []
    if latest_q is not None:
        items_rows = list((await db.execute(
            select(QuoteItem)
            .where(QuoteItem.quote_id == latest_q.id)
            .order_by(QuoteItem.position)
        )).scalars().all())

    return {
        "agent_result": result,
        "quote": latest_q,
        "items": items_rows,
    }


@router.post("/quick-quote", response_model=QuickQuoteResponse)
async def create_quick_quote(
    request: QuickQuoteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Single-step quote (legacy schema, now backed by the unified agent).

    The agent owns the prompt, the calculator, the PDF generation and the
    DB persistence. This route is a thin shape-adapter that turns the
    Quick-Quote request into a free-form mission and reads the resulting
    Quote back as the legacy QuickQuoteResponse.
    """
    try:
        logger.info(
            f"Quick quote (agent) request from user {current_user.id}: "
            f"{request.service_description[:80]}"
        )

        from src.routes.quotes import check_user_quota
        has_quota = await check_user_quota(current_user, db)
        if not has_quota:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Monatliches Kontingent erschöpft. Upgraden Sie auf "
                    "Premium für unbegrenzte Angebote."
                )
            )

        # Build a mission the agent can act on. We bake the cost params
        # (hourly_rate, material_cost_markup) directly into the brief so the
        # agent's faustregeln respect them.
        cost_params = _resolve_cost_params(request, current_user)
        mission_lines = [request.service_description]
        if request.area:
            mission_lines.append(f"Fläche/Umfang: {request.area}")
        if request.additional_info:
            mission_lines.append(f"Zusatzinfo: {request.additional_info}")
        if cost_params.get("hourly_rate") is not None:
            mission_lines.append(f"Stundensatz: {cost_params['hourly_rate']:.2f} EUR/h netto.")
        if cost_params.get("material_cost_markup") is not None:
            mission_lines.append(
                f"Material-Aufschlag: {cost_params['material_cost_markup']:.1f}%."
            )
        if request.customer_name:
            mission_lines.append(f"Kunde: {request.customer_name}")
        mission_lines.append(
            "Erzeuge mir den Voranschlag, ruf save_quote_to_db UND "
            "generate_quote_pdf auf."
        )

        run = await _run_agent_for_quote(
            current_user, db, "\n".join(mission_lines), channel="web",
        )
        quote = run["quote"]
        items = run["items"]

        if quote is None:
            # Agent didn't persist — likely it asked a follow-up question
            # instead of producing a quote. Return a minimal envelope so
            # the frontend can show the agent's text.
            agent_msg = run["agent_result"].get("final_message", "")
            return QuickQuoteResponse(
                quote_id=0,
                quote_number="",
                project_title="(noch kein Voranschlag)",
                items=[],
                subtotal=0.0,
                vat_amount=0.0,
                total_amount=0.0,
                notes=agent_msg or "Der Agent hat keinen Voranschlag erzeugt.",
                recommendations=[],
            )

        subtotal_net = sum(float(i.total_price or 0) for i in items)
        vat_amount = round(subtotal_net * 0.19, 2)
        total_brutto = round(subtotal_net + vat_amount, 2)

        return QuickQuoteResponse(
            quote_id=quote.id,
            quote_number=quote.quote_number,
            project_title=quote.project_title,
            items=[
                QuickQuoteItemResponse(
                    position=int(item.position or i + 1),
                    description=item.description or "",
                    quantity=float(item.quantity or 0),
                    unit=item.unit or "Stk",
                    unit_price=float(item.unit_price or 0),
                    total_price=float(item.total_price or 0),
                    category=str(item.work_type or "labor"),
                )
                for i, item in enumerate(items)
            ],
            subtotal=round(subtotal_net, 2),
            vat_amount=vat_amount,
            total_amount=round(quote.total_amount or total_brutto, 2),
            notes=quote.project_description or "",
            recommendations=[],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating quick quote (agent): {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Fehler bei der Angebotserstellung: {str(e)}",
        )

@router.post("/ask-question", response_model=AIQuestionResponse)
async def ask_follow_up_question(
    request: AIFollowUpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Multi-turn follow-up — backed by the unified Maler-Agent.

    The agent uses its DB-backed conversation memory, so we don't need
    to forward request.conversation_history (legacy frontend state).
    The agent's reply text lands in ``response``; ``needs_more_info`` is
    True when the agent did NOT generate a PDF yet (i.e. is still asking
    clarifying questions), False when a quote+PDF were produced (then the
    "Kostenvoranschlag erstellen" button can show).
    """
    try:
        logger.info(f"ask-question (agent) user={current_user.id}")

        from src.agents.tools.save_quote_to_db import (
            current_conversation_id,
            current_user_id,
        )
        from src.services.agent_service import agent_service

        user_token = current_user_id.set(current_user.id)
        conv_token = current_conversation_id.set(None)
        try:
            result = await agent_service.chat(
                db, current_user, request.question, channel="web",
            )
            current_conversation_id.set(result["conversation_id"])
        finally:
            current_user_id.reset(user_token)
            current_conversation_id.reset(conv_token)

        agent_text = (result.get("final_message") or "").strip() or (
            "Sag mir noch ein paar Details zum Projekt."
        )
        # If the agent already produced a PDF, we have a complete quote
        # and can let the frontend show the "Kostenvoranschlag erstellen"
        # button. Otherwise it's still a clarifying turn.
        produced_quote = bool(result.get("pdf_path"))

        request.conversation_history.append({
            "role": "user",
            "content": request.question,
            "timestamp": datetime.now().isoformat(),
        })
        request.conversation_history.append({
            "role": "assistant",
            "content": agent_text,
            "timestamp": datetime.now().isoformat(),
        })

        pdf_url = _agent_pdf_url(result.get("pdf_path"))
        return AIQuestionResponse(
            response=agent_text,
            needs_more_info=not produced_quote,
            conversation_history=request.conversation_history,
            quote_id=result.get("quote_id"),
            quote_number=result.get("quote_number"),
            pdf_url=pdf_url,
        )

    except Exception as e:
        logger.error(f"Error processing follow-up question: {str(e)}", exc_info=True)
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
        # conversation_history in dicts umwandeln
        history = [msg.model_dump() if hasattr(msg, 'model_dump') else dict(msg) for msg in request.conversation_history] if request.conversation_history else None

        # Dokumente laden und als base64 encodieren
        quote_id = request.project_data.get('quote_id') if request.project_data else None
        document_files = []
        if quote_id:
            result = await db.execute(
                select(DocumentModel)
                .where(DocumentModel.quote_id == quote_id)
                .where(DocumentModel.user_id == current_user.id)
            )
            documents = result.scalars().all()
            for doc in documents:
                try:
                    with open(doc.file_path, "rb") as f:
                        file_bytes = f.read()
                        encoded = base64.b64encode(file_bytes).decode('utf-8')
                        document_files.append({
                            "filename": doc.filename,
                            "mime_type": doc.mime_type,
                            "base64": encoded
                        })
                except Exception as e:
                    logger.error(f"Error reading document file {doc.file_path}: {str(e)}")
        logger.debug("Documents loaded as base64: %d", len(document_files))

        # Phase 2 RAG: retrieve real-world material prices to ground the LLM
        # output. The query is built from the project description + the user's
        # answers so the retrieved context matches the actual project scope.
        material_context = None
        if settings.rag_materials_enabled:
            try:
                rag_query_parts = [str(request.project_data.get("description", ""))]
                for answer in request.answers[:5]:
                    rag_query_parts.append(str(answer.get("answer", answer.get("value", ""))))
                rag_query = " ".join(p for p in rag_query_parts if p).strip()
                if rag_query:
                    region = None
                    if request.customer_address:
                        plz_prefix = "".join(ch for ch in request.customer_address if ch.isdigit())[:1]
                        region = f"DE-{plz_prefix}" if plz_prefix else None
                    materials = await rag_service.retrieve_materials(
                        db=db, query=rag_query, region=region, top_k=5,
                    )
                    material_context = rag_service.materials_to_prompt_context(materials)
                    logger.info("RAG retrieved %d materials for quote", len(material_context))
            except Exception as e:
                logger.warning("RAG retrieval failed, continuing without: %s", e)

        result = await ai_service.process_answers_and_generate_quote(
            project_data=request.project_data,
            answers=request.answers,
            conversation_history=history,
            document_files=document_files,
            material_context=material_context,
            **_resolve_cost_params(request, current_user)
        )
        # Create quote in database
        quote_number = generate_quote_number()
        quote = Quote(
            quote_number=quote_number,
            user_id=current_user.id,
            customer_name=request.customer_name,
            customer_email=request.customer_email,
            customer_phone=request.customer_phone,
            customer_address=request.customer_address,
            project_title=result["quote"]["project_title"],
            project_description=result["quote"].get("project_description"),
            status="draft",
            ai_processing_status="completed",
            created_by_ai=True,
            conversation_history=json.dumps(history, default=default_json) if history is not None else None
        )
        db.add(quote)
        await db.flush()
        # Add quote items
        subtotal_net = 0.0
        quote_items_dicts = []
        for idx, item in enumerate(result["items"], start=1):
            quote_item = QuoteItem(
                quote_id=quote.id,
                position=item.get("position", idx),
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
            subtotal_net += item["total_price"]
            quote_items_dicts.append({
                "id": quote_item.id,
                "quote_id": quote_item.quote_id,
                "position": quote_item.position,
                "description": quote_item.description,
                "quantity": quote_item.quantity,
                "unit": quote_item.unit,
                "unit_price": quote_item.unit_price,
                "total_price": quote_item.total_price,
                "room_name": quote_item.room_name,
                "created_at": quote_item.created_at,
                "updated_at": quote_item.updated_at
            })
        # Quote total is always BRUTTO (subtotal + 19% MwSt) — items hold the
        # net per-position prices. LLM occasionally returns net here despite
        # explicit instructions, so we recompute deterministically.
        quote.total_amount = round(subtotal_net * 1.19, 2)
        await db.commit()
        pdf_data = {
            "quote_number": quote.quote_number,
            "customer_name": quote.customer_name,
            "customer_email": quote.customer_email,
            "customer_phone": quote.customer_phone,
            "customer_address": quote.customer_address,
            "project_title": quote.project_title,
            "project_description": quote.project_description,
            "quote_items": quote_items_dicts
        }
        # Jetzt PDF-Generierung im Threadpool
        pdf_service = PDFService()
        pdf_result = await asyncio.to_thread(pdf_service.generate_quote_pdf, pdf_data)
        # Add final quote generation to conversation
        if request.conversation_history:
            request.conversation_history.append({
                "role": "assistant",
                "content": "Kostenvoranschlag wurde erstellt und als PDF gespeichert",
                "timestamp": datetime.now().isoformat()
            })
        return AIQuoteGenerationResponse(
            quote=result.get("quote", {}),
            items=quote_items_dicts,  # Use the complete quote items with all fields
            notes=result.get("notes", ""),
            recommendations=result.get("recommendations", []),
            conversation_history=request.conversation_history,
            total_amount=quote.total_amount,
            success=True,
            pdf_url=pdf_result.get("pdf_url") if pdf_result.get("success") else None
        )

    except Exception as e:
        logger.error(f"Error generating AI quote: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-document", response_model=DocumentResponse)
async def upload_document_for_analysis(
    file: UploadFile = File(...),
    quote_id: Optional[int] = Form(None),
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
        document = DocumentModel(
            user_id=current_user.id,
            filename=safe_filename,
            original_filename=file.filename,
            file_path=file_path,
            file_size=len(content),
            mime_type=file.content_type,
            processing_status="processing",
            quote_id=quote_id
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
        
        # Erstelle das Response-Objekt explizit aus den Attributen
        resp = DocumentResponse(
            id=document.id,
            user_id=document.user_id,
            filename=document.filename,
            original_filename=document.original_filename,
            file_path=document.file_path,
            file_size=document.file_size,
            mime_type=document.mime_type,
            processing_status=document.processing_status,
            quote_id=document.quote_id,
            created_at=document.created_at,
            updated_at=document.updated_at,
            analysis_result=json.loads(document.analysis_result) if document.analysis_result else None
        )
        return resp
        
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
            select(DocumentModel)
            .where(DocumentModel.id == document_id)
            .where(DocumentModel.user_id == current_user.id)
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

