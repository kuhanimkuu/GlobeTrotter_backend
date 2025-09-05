from typing import Any, Dict, List, Optional
import logging

from ..registry import register
from ..base import EmailAdapter

logger = logging.getLogger(__name__)

@register("notifications.sendgrid")
class SendgridEmailAdapter(EmailAdapter):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self.api_key = self.config.get("api_key")
        self.from_email = self.config.get("from_email")
        self._client = None
        if self.api_key:
            try:
                import sendgrid
                from sendgrid.helpers.mail import Mail  # noqa: F401
                self._client = sendgrid.SendGridAPIClient(self.api_key)
            except Exception:
                logger.debug("SendGrid SDK not available or failed to import.")

    def send_email(self, *, to: List[str], subject: str, html: str, text: Optional[str] = None,
                   from_email: Optional[str] = None, headers: Optional[Dict[str,str]] = None) -> Dict[str, Any]:
        if not self._client:
            raise RuntimeError("SendGrid not configured. Install sendgrid and set api_key.")
        from_address = from_email or self.from_email
        if not from_address:
            raise RuntimeError("SendGrid 'from' email not configured.")

        try:
            from sendgrid.helpers.mail import Mail, Email, To, Content
            message = Mail(
                from_email=from_address,
                to_emails=to,
                subject=subject,
                html_content=html
            )
            # optional plain text
            if text:
                message.add_content(Content("text/plain", text))
            # headers not directly exposed in simple helper; set via message.personalizations if needed
            resp = self._client.send(message)
            return {"status": "QUEUED" if resp.status_code in (200,202) else "FAILED", "provider_id": getattr(resp, "headers", None), "raw": resp}
        except Exception as exc:
            logger.exception("SendGrid send_email failed")
            return {"status": "FAILED", "error": str(exc)}
