from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Dict
import stripe
import os

from src.core.database import get_db
from src.routes.auth import get_current_user
from src.models.models import User, Payment
from src.schemas.schemas import PaymentCreate, PaymentResponse, SuccessResponse

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

# Stripe configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "price_premium_monthly")

@router.post("/create-checkout-session")
async def create_checkout_session(
    success_url: str,
    cancel_url: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create Stripe checkout session for premium upgrade"""
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': STRIPE_PRICE_ID,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=current_user.email,
            metadata={
                'user_id': current_user.id,
                'payment_type': 'premium_upgrade'
            }
        )
        
        # Create payment record
        payment = Payment(
            user_id=current_user.id,
            stripe_session_id=checkout_session.id,
            amount=29.99,  # Premium price
            currency="EUR",
            status="pending",
            payment_type="premium_upgrade",
            description="Premium Subscription"
        )
        
        db.add(payment)
        await db.commit()
        
        return {
            "success": True,
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}"
        )

@router.post("/create-additional-quotes-session")
async def create_additional_quotes_session(
    amount: float,
    description: str,
    success_url: str,
    cancel_url: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create checkout session for additional quotes"""
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': description,
                    },
                    'unit_amount': int(amount * 100),  # Convert to cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=current_user.email,
            metadata={
                'user_id': current_user.id,
                'payment_type': 'additional_quotes',
                'amount': amount
            }
        )
        
        # Create payment record
        payment = Payment(
            user_id=current_user.id,
            stripe_session_id=checkout_session.id,
            amount=amount,
            currency="EUR",
            status="pending",
            payment_type="additional_quotes",
            description=description
        )
        
        db.add(payment)
        await db.commit()
        
        return {
            "success": True,
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}"
        )

@router.get("/quota-info")
async def get_quota_info(current_user: User = Depends(get_current_user)):
    """Get current user quota information"""
    
    total_available = 3  # Free tier
    if current_user.is_premium:
        total_available = -1  # Unlimited
    
    quotes_remaining = max(0, total_available - current_user.quotes_this_month) if total_available > 0 else -1
    
    return {
        "success": True,
        "quota": {
            "is_premium": current_user.is_premium,
            "unlimited": current_user.is_premium,
            "total_available": total_available,
            "quotes_used": current_user.quotes_this_month,
            "quotes_remaining": quotes_remaining,
            "additional_quotes": current_user.additional_quotes
        }
    }

@router.post("/webhook")
async def stripe_webhook(
    request: Dict,
    db: AsyncSession = Depends(get_db)
):
    """Handle Stripe webhook events"""
    
    # In a real implementation, you would verify the webhook signature
    # For now, we'll process the event directly
    
    event_type = request.get('type')
    data = request.get('data', {}).get('object', {})
    
    if event_type == 'checkout.session.completed':
        session_id = data.get('id')
        metadata = data.get('metadata', {})
        user_id = metadata.get('user_id')
        payment_type = metadata.get('payment_type')
        
        if user_id and session_id:
            # Update payment status
            await db.execute(
                update(Payment)
                .where(Payment.stripe_session_id == session_id)
                .values(status="completed")
            )
            
            # Update user based on payment type
            if payment_type == 'premium_upgrade':
                # Upgrade user to premium
                await db.execute(
                    update(User)
                    .where(User.id == int(user_id))
                    .values(is_premium=True)
                )
            elif payment_type == 'additional_quotes':
                # Add additional quotes (assuming 10 quotes for 19.99€)
                amount = float(metadata.get('amount', 19.99))
                additional_quotes = 10 if amount >= 19.99 else 5
                
                await db.execute(
                    update(User)
                    .where(User.id == int(user_id))
                    .values(additional_quotes=User.additional_quotes + additional_quotes)
                )
            
            await db.commit()
    
    return {"status": "success"}

@router.get("/payments", response_model=list[PaymentResponse])
async def get_user_payments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get payment history for current user"""
    
    result = await db.execute(
        select(Payment)
        .where(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
    )
    payments = result.scalars().all()
    
    return payments

