from typing import Any, Dict, Optional
import uuid
import random
from datetime import datetime

from ..registry import register
from ..base import PaymentAdapter


@register("payments.fake")
class FakePaymentAdapter(PaymentAdapter):
 

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self.simulate_failures = self.config.get("simulate_failures", False)


    def create_checkout(
        self,
        *,
        amount: str,
        currency: str,
        customer: Dict[str, str],
        metadata: Dict[str, Any],
        return_urls: Dict[str, str],
    ) -> Dict[str, Any]:
        if self.simulate_failures and random.choice([True, False]):
            raise RuntimeError("Fake checkout failed (simulated)")

        session_id = str(uuid.uuid4())
        return {
            "session_id": session_id,
            "url": return_urls.get("success") or "http://localhost/fake/success",
            "amount": amount,
            "currency": currency,
            "customer": customer,
            "metadata": metadata,
            "created_at": datetime.utcnow().isoformat(),
            "raw": {"adapter": "fake", "mode": "checkout"},
        }

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
                "email": getattr(user, "email", None) if user else (card_details or {}).get("email"),
                "phone": getattr(user, "phone", None) if user else (card_details or {}).get("phone"),
                "name": getattr(user, "name", "Guest") if user else (card_details or {}).get("name", "Guest"),
            },
            metadata={"reference": booking_id, "description": "GlobeTrotter Booking"},
            return_urls={
                "success": f"http://localhost/payment/success?booking={booking_id}",
                "cancel": f"http://localhost/payment/cancel?booking={booking_id}",
            },
        )
        return {
            "status": "SUCCESS",
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
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Simulate refunding a transaction"""
        return {
            "refund_id": str(uuid.uuid4()),
            "txn_ref": txn_ref,
            "amount": amount or "full",
            "reason": reason or "Fake refund",
            "status": "success",
            "processed_at": datetime.utcnow().isoformat(),
            "raw": {"adapter": "fake", "mode": "refund"},
        }

    def verify_webhook(self, *, payload: bytes, headers: Dict[str, str]) -> bool:
        """Fake webhooks are always valid"""
        return True


    def parse_webhook(self, *, payload: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """Simulate parsing a webhook"""
        return {
            "event_type": "fake.payment",
            "event_id": str(uuid.uuid4()),
            "status": "success",
            "amount": "100",
            "currency": "USD",
            "raw": {
                "adapter": "fake",
                "mode": "webhook",
                "payload": payload.decode("utf-8", errors="ignore"),
            },
        }
