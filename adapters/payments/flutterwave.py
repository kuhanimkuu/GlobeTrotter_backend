from typing import Any, Dict, Optional
import requests
from ..registry import register
from ..base import PaymentAdapter

@register("payments.flutterwave")  # ✅ Add registration
class FlutterwaveAdapter(PaymentAdapter):
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self.base_url = "https://api.flutterwave.com/v3"
        self.secret_key = self.config.get("secret_key")
        self.webhook_secret = self.config.get("webhook_secret")

    def create_checkout(self, *, amount: str, currency: str, customer: Dict[str, str],
                       metadata: Dict[str, Any], return_urls: Dict[str, str]) -> Dict[str, Any]:
        # ✅ Implement this abstract method
        pass

    def refund(self, *, txn_ref: str, amount: Optional[str] = None, 
              reason: Optional[str] = None) -> Dict[str, Any]:
        # ✅ Implement this abstract method  
        pass

    def verify_webhook(self, *, payload: bytes, headers: Dict[str, str]) -> bool:
        # ✅ Implement this abstract method
        pass

    def parse_webhook(self, *, payload: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        # ✅ Implement this abstract method
        pass

    #