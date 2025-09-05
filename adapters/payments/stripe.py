from typing import Any, Dict, Optional
from decimal import Decimal
import stripe
from ..registry import register
from ..base import PaymentAdapter

@register("payments.stripe")  
class StripeAdapter(PaymentAdapter):
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        stripe.api_key = self.config.get("api_key")
        self.webhook_secret = self.config.get("webhook_secret")

    def create_checkout(self, *, amount: str, currency: str, customer: Dict[str, str],
                       metadata: Dict[str, Any], return_urls: Dict[str, str]) -> Dict[str, Any]:
       
        try:
            # Convert amount to cents safely
            amount_cents = int(Decimal(amount) * 100)
            
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': currency.lower(),
                        'product_data': {
                            'name': metadata.get('description', 'GlobeTrotter Booking'),
                        },
                        'unit_amount': amount_cents,
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=return_urls.get('success'),
                cancel_url=return_urls.get('cancel'),
                customer_email=customer.get('email'),
                metadata=metadata,
            )
            
            return {
                'session_id': session.id,
                'url': session.url,
                'raw': session
            }
            
        except Exception as e:
            # Handle Stripe errors properly
            raise

    def refund(self, *, txn_ref: str, amount: Optional[str] = None, 
              reason: Optional[str] = None) -> Dict[str, Any]:
        """Create a Stripe refund"""
        try:
            refund_params = {'payment_intent': txn_ref}
            if amount:
                refund_params['amount'] = int(Decimal(amount) * 100)
            if reason:
                refund_params['reason'] = reason
                
            refund = stripe.Refund.create(**refund_params)
            return {'refund_id': refund.id, 'raw': refund}
            
        except Exception as e:
            raise

    def verify_webhook(self, *, payload: bytes, headers: Dict[str, str]) -> bool:
        """Verify Stripe webhook signature"""
        if not self.webhook_secret:
            return False
            
        try:
            signature = headers.get('stripe-signature', '')
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return True
        except stripe.error.SignatureVerificationError:
            return False

    def parse_webhook(self, *, payload: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """Parse Stripe webhook event"""
        try:
            signature = headers.get('stripe-signature', '')
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return {
                'event_type': event.type,
                'event_id': event.id,
                'data': event.data,
                'raw': event
            }
        except Exception as e:
            raise

   