import stripe
from flask import current_app
from datetime import datetime, timedelta
from src.models.models import db, User, Payment
from core.settings import settings

class StripeService:
    def __init__(self):
        stripe.api_key = settings.stripe_secret_key
        self.webhook_secret = settings.stripe_webhook_secret
        self.price_id = settings.stripe_price_id  # Premium subscription price ID
        
    def create_checkout_session(self, user_id, success_url, cancel_url):
        """
        Create a Stripe checkout session for premium upgrade
        """
        try:
            user = User.query.get(user_id)
            if not user:
                return {
                    'success': False,
                    'error': 'User not found'
                }
            
            # Create checkout session
            session = stripe.checkout.Session.create(
                customer_email=user.email,
                payment_method_types=['card'],
                line_items=[
                    {
                        'price': self.price_id,
                        'quantity': 1,
                    }
                ],
                mode='subscription',
                success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=cancel_url,
                metadata={
                    'user_id': str(user_id)
                },
                subscription_data={
                    'metadata': {
                        'user_id': str(user_id)
                    }
                }
            )
            
            return {
                'success': True,
                'checkout_url': session.url,
                'session_id': session.id
            }
            
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': f'Stripe error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Payment error: {str(e)}'
            }
    
    def create_one_time_payment(self, user_id, amount, description, success_url, cancel_url):
        """
        Create a one-time payment session (for additional quotes)
        """
        try:
            user = User.query.get(user_id)
            if not user:
                return {
                    'success': False,
                    'error': 'User not found'
                }
            
            # Create checkout session for one-time payment
            session = stripe.checkout.Session.create(
                customer_email=user.email,
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': 'eur',
                            'product_data': {
                                'name': description,
                                'description': f'Zusätzliche Angebote für {user.company_name or user.username}'
                            },
                            'unit_amount': int(amount * 100),  # Amount in cents
                        },
                        'quantity': 1,
                    }
                ],
                mode='payment',
                success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=cancel_url,
                metadata={
                    'user_id': str(user_id),
                    'payment_type': 'additional_quotes'
                }
            )
            
            return {
                'success': True,
                'checkout_url': session.url,
                'session_id': session.id
            }
            
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': f'Stripe error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Payment error: {str(e)}'
            }
    
    def handle_webhook(self, payload, sig_header):
        """
        Handle Stripe webhook events
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                self._handle_successful_payment(session)
                
            elif event['type'] == 'customer.subscription.created':
                subscription = event['data']['object']
                self._handle_subscription_created(subscription)
                
            elif event['type'] == 'customer.subscription.updated':
                subscription = event['data']['object']
                self._handle_subscription_updated(subscription)
                
            elif event['type'] == 'customer.subscription.deleted':
                subscription = event['data']['object']
                self._handle_subscription_cancelled(subscription)
                
            elif event['type'] == 'invoice.payment_succeeded':
                invoice = event['data']['object']
                self._handle_invoice_payment_succeeded(invoice)
                
            elif event['type'] == 'invoice.payment_failed':
                invoice = event['data']['object']
                self._handle_invoice_payment_failed(invoice)
            
            return {
                'success': True,
                'message': 'Webhook processed successfully'
            }
            
        except ValueError as e:
            return {
                'success': False,
                'error': f'Invalid payload: {str(e)}'
            }
        except stripe.error.SignatureVerificationError as e:
            return {
                'success': False,
                'error': f'Invalid signature: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Webhook error: {str(e)}'
            }
    
    def _handle_successful_payment(self, session):
        """Handle successful payment completion"""
        try:
            user_id = int(session['metadata']['user_id'])
            user = User.query.get(user_id)
            
            if not user:
                current_app.logger.error(f"User {user_id} not found for payment")
                return
            
            # Create payment record
            payment = Payment(
                user_id=user_id,
                stripe_session_id=session['id'],
                stripe_payment_intent_id=session.get('payment_intent'),
                amount=session['amount_total'] / 100,  # Convert from cents
                currency=session['currency'],
                status='completed',
                payment_type=session['metadata'].get('payment_type', 'subscription')
            )
            
            db.session.add(payment)
            
            # Handle different payment types
            if session['metadata'].get('payment_type') == 'additional_quotes':
                # Add additional quotes (e.g., 10 more quotes)
                user.additional_quotes = (user.additional_quotes or 0) + 10
            else:
                # Premium subscription
                user.is_premium = True
                user.premium_until = datetime.utcnow() + timedelta(days=365)  # 1 year
                user.stripe_customer_id = session.get('customer')
            
            db.session.commit()
            current_app.logger.info(f"Payment processed for user {user_id}")
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error processing payment: {str(e)}")
    
    def _handle_subscription_created(self, subscription):
        """Handle subscription creation"""
        try:
            user_id = int(subscription['metadata']['user_id'])
            user = User.query.get(user_id)
            
            if user:
                user.stripe_subscription_id = subscription['id']
                user.is_premium = True
                user.premium_until = datetime.fromtimestamp(subscription['current_period_end'])
                db.session.commit()
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error handling subscription creation: {str(e)}")
    
    def _handle_subscription_updated(self, subscription):
        """Handle subscription updates"""
        try:
            user_id = int(subscription['metadata']['user_id'])
            user = User.query.get(user_id)
            
            if user:
                user.premium_until = datetime.fromtimestamp(subscription['current_period_end'])
                
                # Check if subscription is active
                if subscription['status'] in ['active', 'trialing']:
                    user.is_premium = True
                else:
                    user.is_premium = False
                    
                db.session.commit()
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error handling subscription update: {str(e)}")
    
    def _handle_subscription_cancelled(self, subscription):
        """Handle subscription cancellation"""
        try:
            user_id = int(subscription['metadata']['user_id'])
            user = User.query.get(user_id)
            
            if user:
                user.is_premium = False
                user.stripe_subscription_id = None
                db.session.commit()
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error handling subscription cancellation: {str(e)}")
    
    def _handle_invoice_payment_succeeded(self, invoice):
        """Handle successful invoice payment"""
        try:
            subscription_id = invoice['subscription']
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                user_id = int(subscription['metadata']['user_id'])
                user = User.query.get(user_id)
                
                if user:
                    # Reset monthly quote counter on successful payment
                    user.quotes_this_month = 0
                    user.premium_until = datetime.fromtimestamp(subscription['current_period_end'])
                    db.session.commit()
                    
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error handling invoice payment: {str(e)}")
    
    def _handle_invoice_payment_failed(self, invoice):
        """Handle failed invoice payment"""
        try:
            subscription_id = invoice['subscription']
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                user_id = int(subscription['metadata']['user_id'])
                user = User.query.get(user_id)
                
                if user:
                    # Optionally downgrade user or send notification
                    current_app.logger.warning(f"Payment failed for user {user_id}")
                    
        except Exception as e:
            current_app.logger.error(f"Error handling failed payment: {str(e)}")
    
    def get_customer_portal_url(self, user_id, return_url):
        """
        Create a customer portal session for subscription management
        """
        try:
            user = User.query.get(user_id)
            if not user or not user.stripe_customer_id:
                return {
                    'success': False,
                    'error': 'No Stripe customer found'
                }
            
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=return_url
            )
            
            return {
                'success': True,
                'portal_url': session.url
            }
            
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': f'Stripe error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Portal error: {str(e)}'
            }
    
    def cancel_subscription(self, user_id):
        """
        Cancel a user's subscription
        """
        try:
            user = User.query.get(user_id)
            if not user or not user.stripe_subscription_id:
                return {
                    'success': False,
                    'error': 'No active subscription found'
                }
            
            # Cancel at period end to allow access until paid period expires
            stripe.Subscription.modify(
                user.stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            return {
                'success': True,
                'message': 'Subscription will be cancelled at the end of the current period'
            }
            
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': f'Stripe error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Cancellation error: {str(e)}'
            }

class QuotaService:
    """Service to manage user quote quotas"""
    
    @staticmethod
    def can_create_quote(user):
        """Check if user can create a new quote"""
        if user.is_premium:
            return True
        
        # Check monthly limit for free users
        total_available = 3 + (user.additional_quotes or 0)
        return user.quotes_this_month < total_available
    
    @staticmethod
    def increment_quote_count(user):
        """Increment user's monthly quote count"""
        user.quotes_this_month = (user.quotes_this_month or 0) + 1
        db.session.commit()
    
    @staticmethod
    def get_quota_info(user):
        """Get user's quota information"""
        if user.is_premium:
            return {
                'is_premium': True,
                'unlimited': True,
                'quotes_used': user.quotes_this_month or 0
            }
        
        total_available = 3 + (user.additional_quotes or 0)
        quotes_used = user.quotes_this_month or 0
        
        return {
            'is_premium': False,
            'unlimited': False,
            'total_available': total_available,
            'quotes_used': quotes_used,
            'quotes_remaining': max(0, total_available - quotes_used),
            'additional_quotes': user.additional_quotes or 0
        }

