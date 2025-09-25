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
            raise RuntimeError(f"Stripe checkout creation failed: {e}") from e

   
    def process(
    self,
    *,
    amount: str,
    currency: str,
    booking_id: str,
    card_details: Optional[Dict[str, Any]] = None,
    user: Any = None,
) -> Dict[str, Any]:
        checkout = self.create_checkout(
        amount=amount,
        currency=currency,
        customer={
            "email": getattr(user, "email", None) if user else None,
            "name": getattr(user, "name", "Guest") if user else "Guest",
        },
        metadata={"reference": booking_id},
        return_urls={
            "success": f"http://localhost/payment/success?booking={booking_id}",
            "cancel": f"http://localhost/payment/cancel?booking={booking_id}",
        },
    )
        return {
        "status": "PENDING",  
        "currency": currency,
        "amount": amount,
        "transaction_id": checkout["session_id"],
        "url": checkout["url"],
        "raw": checkout,
    }



    def refund(
    self,
    *,
    txn_ref: str,
    amount: Optional[str] = None,
    reason: Optional[str] = None
) -> Dict[str, Any]:
        """Issue a refund for a Stripe payment intent."""
        try:
            refund_params = {"payment_intent": txn_ref}

            if amount:
                refund_params["amount"] = int(Decimal(amount) * 100)  
            if reason:
                refund_params["reason"] = reason  

            refund = stripe.Refund.create(**refund_params)

            return {
            "refund_id": refund.id,
            "status": refund.status,
            "amount": refund.amount,
            "currency": refund.currency,
            "raw": refund,  
        }

        except Exception as e:
            raise RuntimeError(f"Stripe refund failed: {e}") from e


    def verify_webhook(self, *, payload: bytes, headers: Dict[str, str]) -> bool:
        """Verify Stripe webhook signature"""
        if not self.webhook_secret:
            return False
            
        try:
            signature = headers.get('stripe-signature', '')
            stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return True
        except stripe.error.SignatureVerificationError:
            return False
        except Exception:
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
                'status': getattr(event.data.object, "status", None),
                'amount': getattr(event.data.object, "amount_total", None),
                'currency': getattr(event.data.object, "currency", None),
                'raw': event
            }
        except Exception as e:
            raise RuntimeError(f"Stripe webhook parsing failed: {e}") from e
