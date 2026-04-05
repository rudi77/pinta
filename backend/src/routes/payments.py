from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import stripe
import os
import logging

logger = logging.getLogger(__name__)

from src.core.database import get_db
from src.core.settings import get_settings
from src.routes.auth import get_current_user
from src.models.models import User, Payment, Quote
from src.schemas.schemas import PaymentResponse, SuccessResponse

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

# Stripe configuration
settings = get_settings()
stripe.api_key = settings.stripe_secret_key or os.getenv("STRIPE_SECRET_KEY")
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
                'user_id': str(current_user.id),
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
            detail="Fehler beim Erstellen der Checkout-Session"
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
                'user_id': str(current_user.id),
                'payment_type': 'additional_quotes',
                'amount': str(amount)
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
            detail="Fehler beim Erstellen der Checkout-Session"
        )


@router.post("/quote/{quote_id}/checkout")
async def create_quote_download_checkout(
    quote_id: int,
    success_url: str,
    cancel_url: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create Stripe checkout session for downloading a specific quote PDF.

    Premium users can download for free. Non-premium users must pay per download.
    """

    # Verify quote exists and belongs to user
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

    # Premium users can download for free
    if current_user.is_premium:
        # Mark as paid directly
        await db.execute(
            update(Quote)
            .where(Quote.id == quote_id)
            .values(is_paid=True)
        )
        await db.commit()
        return {
            "success": True,
            "is_premium": True,
            "message": "Premium-Nutzer: Download freigeschaltet"
        }

    # Already paid for this quote
    if quote.is_paid:
        return {
            "success": True,
            "already_paid": True,
            "message": "Kostenvoranschlag bereits bezahlt"
        }

    # Check for existing pending checkout session to avoid duplicates
    existing_payment = await db.execute(
        select(Payment)
        .where(Payment.quote_id == quote_id)
        .where(Payment.user_id == current_user.id)
        .where(Payment.payment_type == "quote_download")
        .where(Payment.status == "pending")
    )
    existing = existing_payment.scalar_one_or_none()
    if existing and existing.stripe_session_id:
        try:
            session = stripe.checkout.Session.retrieve(existing.stripe_session_id)
            if session.status == "open":
                return {
                    "success": True,
                    "checkout_url": session.url,
                    "session_id": session.id,
                    "amount": existing.amount,
                    "currency": existing.currency
                }
        except stripe.error.InvalidRequestError:
            pass  # Session expired or invalid, create a new one

    # Create Stripe checkout session for quote download
    download_price = settings.stripe_quote_download_price

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': f'Kostenvoranschlag {quote.quote_number}',
                        'description': f'PDF-Download: {quote.project_title}',
                    },
                    'unit_amount': int(download_price * 100),  # Convert to cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=current_user.email,
            metadata={
                'user_id': str(current_user.id),
                'payment_type': 'quote_download',
                'quote_id': str(quote_id),
            }
        )

        # Create payment record linked to the quote
        payment = Payment(
            user_id=current_user.id,
            quote_id=quote_id,
            stripe_session_id=checkout_session.id,
            amount=download_price,
            currency="EUR",
            status="pending",
            payment_type="quote_download",
            description=f"PDF-Download: {quote.quote_number}"
        )

        db.add(payment)
        await db.commit()

        return {
            "success": True,
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id,
            "amount": download_price,
            "currency": "EUR"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fehler beim Erstellen der Checkout-Session: {str(e)}"
        )


@router.get("/quote/{quote_id}/status")
async def get_quote_payment_status(
    quote_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Check whether a quote has been paid for (download unlocked)."""

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

    return {
        "quote_id": quote_id,
        "is_paid": quote.is_paid,
        "is_premium": current_user.is_premium,
        "download_allowed": quote.is_paid or current_user.is_premium,
        "download_price": settings.stripe_quote_download_price if not (quote.is_paid or current_user.is_premium) else 0
    }


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
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle Stripe webhook events.

    Requires STRIPE_WEBHOOK_SECRET to be configured and a valid
    stripe-signature header on every request.
    """

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    webhook_secret = settings.stripe_webhook_secret

    if not webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET is not configured – rejecting webhook")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured"
        )

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header"
        )

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature"
        )

    event_type = event['type']
    data = event['data']['object']

    if event_type == 'checkout.session.completed':
        session_id = data['id']
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

            if payment_type == 'premium_upgrade':
                await db.execute(
                    update(User)
                    .where(User.id == int(user_id))
                    .values(is_premium=True)
                )
            elif payment_type == 'additional_quotes':
                amount = float(metadata.get('amount', 19.99))
                additional_quotes = 10 if amount >= 19.99 else 5
                await db.execute(
                    update(User)
                    .where(User.id == int(user_id))
                    .values(additional_quotes=User.additional_quotes + additional_quotes)
                )
            elif payment_type == 'quote_download':
                quote_id = metadata.get('quote_id')
                if quote_id:
                    await db.execute(
                        update(Quote)
                        .where(Quote.id == int(quote_id))
                        .values(is_paid=True)
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
