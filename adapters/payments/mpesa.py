from typing import Any, Dict, Optional
from datetime import datetime
import requests
import base64
import json
import hmac
import hashlib

from ..registry import register
from ..base import PaymentAdapter


@register("payments.mpesa") 
class MpesaAdapter(PaymentAdapter):
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self.base_url = self.config.get("base_url", "https://sandbox.safaricom.co.ke")
        self.consumer_key = self.config.get("consumer_key")
        self.consumer_secret = self.config.get("consumer_secret")
        self.shortcode = self.config.get("shortcode")
        self.passkey = self.config.get("passkey")
        self.callback_url = self.config.get("callback_url")
        self.webhook_secret = self.config.get("webhook_secret", "mpesa_secret")  


    def _get_token(self) -> str:
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        r = requests.get(url, auth=(self.consumer_key, self.consumer_secret), timeout=10)
        r.raise_for_status()
        return r.json()["access_token"]


    def create_checkout(
        self,
        *,
        amount: str,
        currency: str,
        customer: Dict[str, str],
        metadata: Dict[str, Any],
        return_urls: Dict[str, str]
    ) -> Dict[str, Any]:
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password_str = f"{self.shortcode}{self.passkey}{timestamp}"
        password = base64.b64encode(password_str.encode()).decode()

        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": customer.get("phone"),
            "PartyB": self.shortcode,
            "PhoneNumber": customer.get("phone"),
            "CallBackURL": self.callback_url,
            "AccountReference": metadata.get("reference", "GlobeTrotter"),
            "TransactionDesc": metadata.get("description", "Travel booking"),
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
        user: Any = None
    ) -> Dict[str, Any]:
        resp = self.create_checkout(
            amount=amount,
            currency=currency,
            customer={
                "phone": getattr(user, "phone", None) or (card_details.get("phone") if card_details else None),
                "email": getattr(user, "email", None) if hasattr(user, "email") else None,
            },
            metadata={"reference": booking_id, "description": "GlobeTrotter Booking"},
            return_urls={
                "success": f"https://yourfrontend.com/payment/success?booking={booking_id}",
                "cancel": f"https://yourfrontend.com/payment/cancel?booking={booking_id}",
            },
        )

        return {
            "status": "PENDING",
            "amount": amount,
            "currency": currency,
            "transaction_id": resp.get("CheckoutRequestID"),
            "redirect_url": None, 
            "raw": resp,
        }


    def refund(
        self,
        *,
        txn_ref: str,
        amount: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/mpesa/reversal/v1/request"

        payload = {
            "Initiator": self.config.get("initiator", "testapi"),
            "SecurityCredential": self.config.get("security_credential", "dummy"),
            "CommandID": "TransactionReversal",
            "TransactionID": txn_ref,
            "Amount": amount or "1",
            "ReceiverParty": self.shortcode,
            "RecieverIdentifierType": "11",
            "ResultURL": self.callback_url,
            "QueueTimeOutURL": self.callback_url,
            "Remarks": reason or "Customer requested refund",
            "Occasion": "Reversal",
        }

        r = requests.post(url, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        resp = r.json()

        return {
            "status": "SUCCESS" if resp.get("ResponseCode") == "0" else "FAILED",
            "transaction_id": txn_ref,
            "raw": resp,
        }

    def verify_webhook(self, *, payload: bytes, headers: Dict[str, str]) -> bool:
        try:
            signature = headers.get("X-MPesa-Signature")
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
            callback = data.get("Body", {}).get("stkCallback", {})

            result_code = callback.get("ResultCode")
            metadata_items = callback.get("CallbackMetadata", {}).get("Item", [])

           
            amount = None
            for item in metadata_items:
                if item.get("Name") == "Amount":
                    amount = item.get("Value")
                    break

            return {
                "event_type": "mpesa.payment",
                "event_id": callback.get("CheckoutRequestID"),
                "status": "SUCCESS" if result_code == 0 else "FAILED",
                "amount": amount,
                "currency": "KES",
                "transaction_id": callback.get("MpesaReceiptNumber"),
                "raw": data,
            }
        except Exception as e:
            return {"error": str(e), "raw": payload}
