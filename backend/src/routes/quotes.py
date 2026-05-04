from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import uuid
import json

# Agent-generated PDFs land here (same path as routes/agent.py:_QUOTES_DIR).
_AGENT_QUOTES_DIR = (
    Path(__file__).resolve().parents[2] / ".taskforce_maler" / "quotes"
)

from src.core.database import get_db
from src.routes.auth import get_current_user
from src.models.models import User, Quote, QuoteItem
from src.schemas.schemas import (
    QuoteCreate, QuoteUpdate, QuoteResponse, QuoteItemCreate, 
    SuccessResponse, ErrorResponse, GenerateQuoteAIRequest,
    PDFGenerationOptions, PDFGenerationResponse, ExportOptions, ExportResponse
)
from src.services.ai_service import AIService
from src.services.professional_pdf_service import ProfessionalPDFService, QuoteExportService

router = APIRouter(prefix="/api/v1/quotes", tags=["quotes"])
ai_service = AIService()
pdf_service = ProfessionalPDFService()
export_service = QuoteExportService()

def generate_quote_number() -> str:
    """Generate unique quote number: KV-YYYYMMDD-HHMMSS-<random>."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"KV-{timestamp}-{suffix}"

async def check_user_quota(user: User, db: AsyncSession) -> bool:
    """Check if user can create a new quote"""
    if user.is_premium:
        return True
    
    # Check free tier quota (3 per month)
    if user.quotes_this_month >= 3:
        # Check additional quotes
        if user.additional_quotes > 0:
            # Deduct from additional quotes
            await db.execute(
                update(User)
                .where(User.id == user.id)
                .values(additional_quotes=User.additional_quotes - 1)
            )
            await db.commit()
            return True
        return False
    
    # User hasn't reached monthly limit, increment counter
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(quotes_this_month=User.quotes_this_month + 1)
    )
    await db.commit()
    return True

def _parse_conversation_history(raw_history):
    if not raw_history:
        return []
    try:
        parsed = json.loads(raw_history)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [
        message for message in parsed
        if isinstance(message, dict) and "role" in message and "content" in message
    ]


def quote_to_response(quote):
    return {
        "id": quote.id,
        "quote_number": quote.quote_number,
        "user_id": quote.user_id,
        "customer_name": quote.customer_name,
        "customer_email": quote.customer_email,
        "customer_phone": quote.customer_phone,
        "customer_address": quote.customer_address,
        "project_title": quote.project_title,
        "project_description": quote.project_description or "",
        "total_amount": quote.total_amount,
        "status": quote.status,
        "created_by_ai": quote.created_by_ai,
        "is_paid": quote.is_paid,
        "conversation_history": _parse_conversation_history(quote.conversation_history),
        "items": [
            {
                "id": item.id,
                "quote_id": item.quote_id,
                "position": item.position,
                "description": item.description,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
                "room_name": item.room_name,
                "created_at": item.created_at,
                "updated_at": item.updated_at
            }
            for item in quote.quote_items
        ],
        "created_at": quote.created_at,
        "updated_at": quote.updated_at,
    }

@router.get("/", response_model=List[QuoteResponse])
async def get_quotes(
    status_filter: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all quotes for current user. Supports `q` substring search across
    customer_name, project_title and quote_number (case-insensitive)."""

    query = select(Quote).where(Quote.user_id == current_user.id)

    if status_filter:
        query = query.where(Quote.status == status_filter)

    if q:
        from sqlalchemy import or_, func as sa_func
        needle = f"%{q.lower()}%"
        query = query.where(
            or_(
                sa_func.lower(Quote.customer_name).like(needle),
                sa_func.lower(Quote.project_title).like(needle),
                sa_func.lower(Quote.quote_number).like(needle),
            )
        )

    query = query.options(selectinload(Quote.quote_items)).order_by(Quote.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    quotes = result.scalars().all()

    return [quote_to_response(q) for q in quotes]

@router.post("/", response_model=QuoteResponse)
async def create_quote(
    quote_data: QuoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new quote"""

    # Check user quota
    if not await check_user_quota(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quote limit reached. Please upgrade to premium or purchase additional quotes."
        )
    
    # Create quote
    quote_number = generate_quote_number()
    
    # Convert conversation history to JSON string if present
    conversation_history = None
    if quote_data.conversation_history:
        conversation_history = json.dumps([msg.model_dump() for msg in quote_data.conversation_history])
    
    quote = Quote(
        quote_number=quote_number,
        user_id=current_user.id,
        customer_name=quote_data.customer_name,
        customer_email=quote_data.customer_email,
        customer_phone=quote_data.customer_phone,
        customer_address=quote_data.customer_address,
        project_title=quote_data.project_title,
        project_description=quote_data.project_description,
        status="draft",
        ai_processing_status="pending",
        created_by_ai=quote_data.created_by_ai,
        conversation_history=conversation_history
    )
    
    db.add(quote)
    await db.flush()  # This will get us the quote.id without committing
    
    # Add quote items
    total_amount = 0.0
    for idx, item_data in enumerate(quote_data.items, start=1):
        quote_item = QuoteItem(
            quote_id=quote.id,
            position=item_data.position if item_data.position is not None else idx,
            description=item_data.description,
            quantity=item_data.quantity,
            unit=item_data.unit or "Stk",
            unit_price=item_data.unit_price,
            total_price=item_data.total_price,
            room_name=item_data.room_name,
            area_sqm=item_data.area_sqm,
            work_type=item_data.work_type,
        )
        db.add(quote_item)
        total_amount += item_data.total_price
    
    # Update quote with total amount
    quote.total_amount = total_amount
    quote.ai_processing_status = "completed"
    
    await db.commit()
    
    # Load the complete quote with items
    result = await db.execute(
        select(Quote)
        .where(Quote.id == quote.id)
        .options(selectinload(Quote.quote_items))
    )
    quote = result.scalar_one()

    return quote_to_response(quote)

@router.get("/{quote_id}", response_model=QuoteResponse)
async def get_quote(
    quote_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get specific quote"""
    result = await db.execute(
        select(Quote)
        .where(Quote.id == quote_id)
        .where(Quote.user_id == current_user.id)
        .options(selectinload(Quote.quote_items))
    )
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )

    return quote_to_response(quote)

@router.put("/{quote_id}", response_model=QuoteResponse)
async def update_quote(
    quote_id: int,
    quote_update: QuoteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a quote"""
    
    result = await db.execute(
        select(Quote)
        .where(Quote.id == quote_id)
        .where(Quote.user_id == current_user.id)
    )
    quote = result.scalar_one_or_none()
    
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    # Update quote
    update_data = quote_update.model_dump(exclude_unset=True)
    
    # Convert conversation history to JSON string if present
    if "conversation_history" in update_data:
        update_data["conversation_history"] = json.dumps(
            [msg.model_dump() for msg in update_data["conversation_history"]]
        )
    
    if update_data:
        await db.execute(
            update(Quote)
            .where(Quote.id == quote_id)
            .values(**update_data)
        )
        await db.commit()
        await db.refresh(quote)
    
    # Load quote items
    items_result = await db.execute(
        select(QuoteItem)
        .where(QuoteItem.quote_id == quote.id)
        .order_by(QuoteItem.position)
    )
    quote.quote_items = items_result.scalars().all()
    
    return quote_to_response(quote)

@router.delete("/{quote_id}", response_model=SuccessResponse)
async def delete_quote(
    quote_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a quote"""
    
    result = await db.execute(
        select(Quote)
        .where(Quote.id == quote_id)
        .where(Quote.user_id == current_user.id)
    )
    quote = result.scalar_one_or_none()
    
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    await db.delete(quote)
    await db.commit()
    
    return SuccessResponse(message="Quote deleted successfully")

@router.post("/{quote_id}/generate-ai", response_model=QuoteResponse)
async def generate_quote_with_ai(
    quote_id: int,
    request: GenerateQuoteAIRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate quote items using AI based on project description"""
    
    result = await db.execute(
        select(Quote)
        .where(Quote.id == quote_id)
        .where(Quote.user_id == current_user.id)
    )
    quote = result.scalar_one_or_none()
    
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    try:
        # Update processing status
        await db.execute(
            update(Quote)
            .where(Quote.id == quote_id)
            .values(ai_processing_status="processing")
        )
        await db.commit()
        
        # Analyze with AI
        analysis = await ai_service.analyze_project_description(
            description=request.project_description, 
            context="quote_generation"
        )
        
        # Clear existing quote items
        existing_items = (await db.execute(
            select(QuoteItem).where(QuoteItem.quote_id == quote_id)
        )).scalars().all()
        
        for item in existing_items:
            await db.delete(item)
        
        # Create new quote items from AI suggestions
        total_amount = 0.0
        suggested_items = analysis.get("suggested_items", [])
        
        for i, item_data in enumerate(suggested_items, 1):
            quote_item = QuoteItem(
                quote_id=quote.id,
                position=i,
                description=item_data.get("description", ""),
                quantity=item_data.get("quantity", 1),
                unit=item_data.get("unit", "Stk"),
                unit_price=item_data.get("unit_price", 0),
                total_price=item_data.get("total_price", 0),
                work_type=item_data.get("work_type", "")
            )
            db.add(quote_item)
            total_amount += quote_item.total_price
        
        # Update quote
        await db.execute(
            update(Quote)
            .where(Quote.id == quote_id)
            .values(
                total_amount=total_amount,
                ai_processing_status="completed",
                project_description=request.project_description
            )
        )
        
        await db.commit()
        
        # Load the complete quote with items
        result = await db.execute(
            select(Quote)
            .where(Quote.id == quote.id)
            .options(selectinload(Quote.quote_items))
        )
        quote = result.scalar_one()
        
        return quote_to_response(quote)
        
    except Exception as e:
        # Update status to failed
        await db.execute(
            update(Quote)
            .where(Quote.id == quote_id)
            .values(ai_processing_status="failed")
        )
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI quote generation failed: {str(e)}"
        )

@router.post("/{quote_id}/duplicate", response_model=QuoteResponse)
async def duplicate_quote(
    quote_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Duplicate an existing quote"""

    # Check user quota
    if not await check_user_quota(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quote limit reached. Please upgrade to premium or purchase additional quotes."
        )
    
    result = await db.execute(
        select(Quote)
        .where(Quote.id == quote_id)
        .where(Quote.user_id == current_user.id)
    )
    original_quote = result.scalar_one_or_none()
    
    if not original_quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    # Create new quote
    new_quote_number = generate_quote_number()
    
    new_quote = Quote(
        quote_number=new_quote_number,
        user_id=current_user.id,
        customer_name=f"Kopie - {original_quote.customer_name}",
        customer_email=original_quote.customer_email,
        customer_phone=original_quote.customer_phone,
        customer_address=original_quote.customer_address,
        project_title=f"Kopie - {original_quote.project_title}",
        project_description=original_quote.project_description,
        total_amount=original_quote.total_amount,
        labor_hours=original_quote.labor_hours,
        hourly_rate=original_quote.hourly_rate,
        material_cost=original_quote.material_cost,
        additional_costs=original_quote.additional_costs,
        status="draft",
        ai_processing_status="completed"
    )
    
    db.add(new_quote)
    await db.commit()
    await db.refresh(new_quote)
    
    # Copy quote items
    items_result = await db.execute(
        select(QuoteItem)
        .where(QuoteItem.quote_id == quote_id)
        .order_by(QuoteItem.position)
    )
    original_items = items_result.scalars().all()
    
    for original_item in original_items:
        new_item = QuoteItem(
            quote_id=new_quote.id,
            position=original_item.position,
            description=original_item.description,
            quantity=original_item.quantity,
            unit=original_item.unit,
            unit_price=original_item.unit_price,
            total_price=original_item.total_price,
            room_name=original_item.room_name,
            area_sqm=original_item.area_sqm,
            work_type=original_item.work_type
        )
        db.add(new_item)
    
    await db.commit()
    
    # Load new quote with items
    items_result = await db.execute(
        select(QuoteItem)
        .where(QuoteItem.quote_id == new_quote.id)
        .order_by(QuoteItem.position)
    )
    new_quote.quote_items = items_result.scalars().all()
    
    return quote_to_response(new_quote)

@router.post(
    "/{quote_id}/pdf/generate",
    response_model=PDFGenerationResponse,
    deprecated=True,
)
async def generate_quote_pdf(
    quote_id: int,
    options: Optional[PDFGenerationOptions] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """DEPRECATED. Use GET /quotes/{id}/agent-pdf-info → GET /agent/pdf/{name}.

    Legacy ProfessionalPDFService path; agent-generated quotes won't have
    a file under uploads/pdfs/, so this returns 404 for them.
    """
    
    # Get quote with items
    result = await db.execute(
        select(Quote)
        .where(Quote.id == quote_id)
        .where(Quote.user_id == current_user.id)
        .options(selectinload(Quote.quote_items))
    )
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )

    try:
        # Convert quote to dict format expected by PDF service
        quote_data = quote_to_response(quote)
        
        # Generate PDF
        options_dict = options.model_dump() if options else {}
        pdf_result = await pdf_service.generate_professional_quote_pdf(quote_data, options_dict)
        
        if pdf_result['success']:
            return {
                'success': True,
                'message': 'PDF generated successfully',
                'pdf_info': pdf_result
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=pdf_result['error']
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {str(e)}"
        )

@router.get("/{quote_id}/pdf/download", deprecated=True)
async def download_quote_pdf(
    quote_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """DEPRECATED. Use GET /quotes/{id}/agent-pdf-info → GET /agent/pdf/{name}.

    Legacy file lookup in uploads/pdfs/; agent-generated quotes are in
    .taskforce_maler/quotes/ and won't be found here.
    """

    # Verify quote ownership
    result = await db.execute(
        select(Quote)
        .where(Quote.id == quote_id)
        .where(Quote.user_id == current_user.id)
    )
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kostenvoranschlag nicht gefunden"
        )

    # Check payment status - premium users or paid quotes can download
    if not current_user.is_premium and not quote.is_paid:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Bezahlung erforderlich. Bitte bezahlen Sie den Kostenvoranschlag, bevor Sie ihn herunterladen."
        )

    # Look for existing PDF file
    from pathlib import Path
    pdf_dir = Path('uploads/pdfs')

    # Find the most recent PDF for this quote
    pdf_files = list(pdf_dir.glob(f"{quote.quote_number}_*.pdf"))

    if not pdf_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF nicht gefunden. Bitte generieren Sie zuerst das PDF."
        )

    # Get the most recent PDF
    latest_pdf = max(pdf_files, key=lambda p: p.stat().st_mtime)

    return FileResponse(
        path=latest_pdf,
        filename=f"{quote.quote_number}.pdf",
        media_type='application/pdf'
    )


@router.get("/{quote_id}/agent-pdf-info")
async def get_agent_pdf_info(
    quote_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Resolve a Quote → its agent-generated PDF in `.taskforce_maler/quotes/`.

    Returns `{pdf_url, pdf_filename}` so the frontend can hand the URL to
    `GET /api/v1/agent/pdf/{name}` (auth-gated, path-traversal-protected).
    """
    result = await db.execute(
        select(Quote)
        .where(Quote.id == quote_id)
        .where(Quote.user_id == current_user.id)
    )
    quote = result.scalar_one_or_none()
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kostenvoranschlag nicht gefunden",
        )

    if not _AGENT_QUOTES_DIR.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF nicht gefunden. Bitte über den Chat erneut anstoßen.",
        )

    matches = sorted(
        (p for p in _AGENT_QUOTES_DIR.glob(f"*{quote.quote_number}*.pdf") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF nicht gefunden. Bitte über den Chat erneut anstoßen.",
        )

    filename = matches[0].name
    return {
        "pdf_filename": filename,
        "pdf_url": f"/api/v1/agent/pdf/{filename}",
    }


@router.post("/{quote_id}/export", response_model=ExportResponse)
async def export_quote(
    quote_id: int,
    export_options: ExportOptions,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Export quote in various formats (PDF, JSON, CSV)"""

    # Get quote with items
    result = await db.execute(
        select(Quote)
        .where(Quote.id == quote_id)
        .where(Quote.user_id == current_user.id)
        .options(selectinload(Quote.quote_items))
    )
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )

    # PDF export requires payment (same rules as PDF download)
    if export_options.format_type == "pdf":
        if not current_user.is_premium and not quote.is_paid:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Bezahlung erforderlich. Bitte bezahlen Sie den Kostenvoranschlag, bevor Sie ihn als PDF exportieren."
            )

    try:
        # Convert quote to dict format
        quote_data = quote_to_response(quote)
        
        # Export in requested format
        options_dict = export_options.model_dump(exclude={'format_type'})
        export_result = await export_service.export_quote(quote_data, export_options.format_type, options_dict)
        
        if export_result['success']:
            return {
                'success': True,
                'message': f'Quote exported as {export_options.format_type.upper()} successfully',
                'export_info': export_result
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=export_result['error']
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )

