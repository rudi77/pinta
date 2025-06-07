from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime
import uuid
import json

from src.core.database import get_db
from src.routes.auth import get_current_user
from src.models.models import User, Quote, QuoteItem
from src.schemas.schemas import (
    QuoteCreate, QuoteUpdate, QuoteResponse, QuoteItemCreate, 
    SuccessResponse, ErrorResponse, GenerateQuoteAIRequest
)
from src.services.ai_service import AIService

router = APIRouter()
ai_service = AIService()

def generate_quote_number() -> str:
    """Generate unique quote number"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"KV-{timestamp}"

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

@router.get("/", response_model=List[QuoteResponse])
async def get_quotes(
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all quotes for current user"""
    
    query = select(Quote).where(Quote.user_id == current_user.id)
    
    if status_filter:
        query = query.where(Quote.status == status_filter)
    
    query = query.options(selectinload(Quote.quote_items)).order_by(Quote.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    quotes = result.scalars().all()
    
    return quotes

@router.post("/", response_model=QuoteResponse)
async def create_quote(
    quote_data: QuoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new quote"""
    
    # Check user quota
    # if not await check_user_quota(current_user, db):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Quote limit reached. Please upgrade to premium or purchase additional quotes."
    #     )
    
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
    for item_data in quote_data.quote_items:
        quote_item = QuoteItem(
            quote_id=quote.id,
            position=item_data.position,
            description=item_data.description,
            quantity=item_data.quantity,
            unit=item_data.unit,
            unit_price=item_data.unit_price,
            total_price=item_data.total_price,
            room_name=item_data.room_name,
            area_sqm=item_data.area_sqm,
            work_type=item_data.work_type
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
    
    return quote

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
    )
    quote = result.scalar_one_or_none()
    
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    # Load quote items
    items_result = await db.execute(
        select(QuoteItem)
        .where(QuoteItem.quote_id == quote.id)
        .order_by(QuoteItem.position)
    )
    quote.quote_items = items_result.scalars().all()
    
    return quote

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
    
    return quote

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
        
        return quote
        
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
    # if not await check_user_quota(current_user, db):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Quote limit reached. Please upgrade to premium or purchase additional quotes."
    #     )
    
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
    
    return new_quote

