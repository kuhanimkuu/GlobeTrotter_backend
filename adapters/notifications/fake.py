from typing import Any, Dict, List, Optional
from ..registry import register
from ..base import SmsAdapter, EmailAdapter, PushAdapter

@register("notifications.fake_sms")
class FakeSmsAdapter(SmsAdapter):
    def send_sms(self, *, to: str, message: str, sender_id: Optional[str] = None) -> Dict[str, Any]:
        return {"status": "SENT", "provider_id": "fake_sms_1", "raw": {"to": to, "message": message}}

@register("notifications.fake_email")
class FakeEmailAdapter(EmailAdapter):
    def send_email(self, *, to: List[str], subject: str, html: str, text: Optional[str] = None,
                   from_email: Optional[str] = None, headers: Optional[Dict[str,str]] = None) -> Dict[str, Any]:
        return {"status": "QUEUED", "provider_id": "fake_email_1", "raw": {"to": to, "subject": subject}}

@register("notifications.fake_push")
class FakePushAdapter(PushAdapter):
    def send_push(self, *, token: str, title: str, body: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"status": "SENT", "provider_id": "fake_push_1", "raw": {"token": token, "title": title, "body": body}}
