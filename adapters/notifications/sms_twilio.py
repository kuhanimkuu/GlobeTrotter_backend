from typing import Any, Dict, Optional
import logging

from ..registry import register
from ..base import SmsAdapter

logger = logging.getLogger(__name__)

@register("notifications.twilio")
class TwilioSmsAdapter(SmsAdapter):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self.account_sid = self.config.get("account_sid")
        self.auth_token = self.config.get("auth_token")
        self.from_number = self.config.get("from_number")
        self._client = None
        if self.account_sid and self.auth_token:
            try:
                import twilio.rest as _twilio_rest
                self._client = _twilio_rest.Client(self.account_sid, self.auth_token)
            except Exception:
                # SDK missing or import error — keep adapter constructible but non-functional until configured
                logger.debug("Twilio SDK not available or failed to import.")

    def send_sms(self, *, to: str, message: str, sender_id: Optional[str] = None) -> Dict[str, Any]:
        if not self._client:
            raise RuntimeError("Twilio client not configured. Install twilio and set credentials.")

        from_number = sender_id or self.from_number
        if not from_number:
            raise RuntimeError("Twilio 'from' number is not configured.")

        try:
            msg = self._client.messages.create(body=message, to=to, from_=from_number)
            return {"status": "SENT", "provider_id": getattr(msg, "sid", None), "raw": msg}
        except Exception as exc:
            logger.exception("Twilio send_sms failed")
            return {"status": "FAILED", "error": str(exc)}
