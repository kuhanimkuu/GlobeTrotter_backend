from typing import Any, Dict, Optional
import requests
import json
import hmac
import hashlib
from ..registry import register
from ..base import PaymentAdapter


@register("payments.flutterwave") 
class FlutterwaveAdapter(PaymentAdapter):
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self.base_url = "https://api.flutterwave.com/v3"
        self.secret_key = self.config.get("secret_key")
        self.webhook_secret = self.config.get("webhook_secret")

    def create_checkout(
        self,
        *,
        amount: str,
        currency: str,
        customer: Dict[str, str],
        metadata: Dict[str, Any],
        return_urls: Dict[str, str]
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/payments"
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "tx_ref": metadata.get("reference", "globetrotter_txn"),
            "amount": amount,
            "currency": currency,
            "redirect_url": return_urls.get("success"),
            "customer": {
                "email": customer.get("email"),
                "phonenumber": customer.get("phone"),
                "name": customer.get("name", "GlobeTrotter User"),
            },
            "customizations": {
                "title": "GlobeTrotter Booking",
                "description": metadata.get("description", "Travel booking"),
            },
        }

        r = requests.post(url, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()

    def process(
    self,
    *,
    amount: str,
    currency: str,
    booking_id: str,
    card_details: Optional[Dict[str, Any]] = None,
    user: Any = None,
) -> Dict[str, Any]:
        response = self.create_checkout(
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
        data = response.get("data", {})
        return {
        "status": "PENDING" if response.get("status") == "success" else "FAILED",
        "currency": data.get("currency", currency),
        "amount": str(data.get("amount", amount)),
        "transaction_id": data.get("tx_ref", booking_id),
        "url": data.get("link"),
        "raw": response,
    }

    def refund(
        self,
        *,
        txn_ref: str,
        amount: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/refunds"
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "transaction_reference": txn_ref,
            "amount": amount,
            "reason": reason or "Customer requested refund",
        }

        r = requests.post(url, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()

    def verify_webhook(self, *, payload: bytes, headers: Dict[str, str]) -> bool:
        try:
            signature = headers.get("verif-hash")
            if not signature or not self.webhook_secret:
                return True 
            expected = hmac.new(
                self.webhook_secret.encode(), payload, hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception:
            return False

    def parse_webhook(self, *, payload: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        try:
            data = json.loads(payload.decode("utf-8"))
            return {
                "event_type": "flutterwave.payment",
                "event_id": data.get("tx_ref"),
                "status": data.get("status"),
                "amount": data.get("amount"),
                "currency": data.get("currency"),
                "transaction_id": data.get("flw_ref"),
                "raw": data,
            }
        except Exception as e:
            return {"error": str(e), "raw": payload}
