from typing import Any, Dict, Optional
from datetime import datetime
import requests
from ..registry import register
from ..base import PaymentAdapter

@register("payments.mpesa")  # ✅ Add registration
class MpesaAdapter(PaymentAdapter):
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self.base_url = self.config.get("base_url", "https://sandbox.safaricom.co.ke")
        self.consumer_key = self.config.get("consumer_key")
        self.consumer_secret = self.config.get("consumer_secret")
        self.shortcode = self.config.get("shortcode")
        self.passkey = self.config.get("passkey")
        self.callback_url = self.config.get("callback_url")

    def _get_token(self):
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        r = requests.get(url, auth=(self.consumer_key, self.consumer_secret), timeout=10)
        r.raise_for_status()
        return r.json()["access_token"]

    def create_checkout(self, *, amount: str, currency: str, customer: Dict[str, str],
                       metadata: Dict[str, Any], return_urls: Dict[str, str]) -> Dict[str, Any]:
        # ✅ Implement STK push for MPesa
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        # Generate password (shortcode + passkey + timestamp)
        import base64
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

    # ✅ Implement other required methods...
    def refund(self, *, txn_ref: str, amount: Optional[str] = None, 
              reason: Optional[str] = None) -> Dict[str, Any]:
        # MPesa reversal implementation
        pass

    def verify_webhook(self, *, payload: bytes, headers: Dict[str, str]) -> bool:
        # MPesa webhook validation
        pass

    def parse_webhook(self, *, payload: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        # MPesa webhook parsing
        pass

 