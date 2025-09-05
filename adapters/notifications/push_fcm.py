from typing import Any, Dict, Optional
import logging

from ..registry import register
from ..base import PushAdapter

logger = logging.getLogger(__name__)

@register("notifications.fcm")
class FcmPushAdapter(PushAdapter):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self.service_account_json = self.config.get("service_account_json")
        self._initialized = False
        if self.service_account_json:
            try:
                import firebase_admin
                from firebase_admin import credentials, messaging
                # If the app is already initialized it's OK; we just grab messaging
                if not firebase_admin._apps:
                    cred = credentials.Certificate(self.service_account_json) if isinstance(self.service_account_json, str) else credentials.Certificate(self.service_account_json)
                    firebase_admin.initialize_app(cred)
                self._initialized = True
            except Exception:
                logger.debug("firebase-admin not installed / failed to initialize")

    def send_push(self, *, token: str, title: str, body: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("FCM not configured (service_account_json missing or firebase_admin not installed)")
        try:
            from firebase_admin import messaging
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                token=token,
                data={k: str(v) for k,v in (data or {}).items()}
            )
            resp = messaging.send(message)
            return {"status": "SENT", "provider_id": resp}
        except Exception as exc:
            logger.exception("FCM send_push failed")
            return {"status": "FAILED", "error": str(exc)}
