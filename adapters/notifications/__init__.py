
from importlib import import_module
import logging
from typing import List

logger = logging.getLogger(__name__)

_MODULES = (
    "adapters.notifications.sms_twilio",
    "adapters.notifications.email_sendgrid",
    "adapters.notifications.push_fcm",
    "adapters.notifications.fake",
)

for mod in _MODULES:
    try:
        import_module(mod)
    except Exception as exc:
        logger.debug("Could not import notifications adapter %s: %s", mod, exc)


def available_notification_adapters() -> List[str]:
    try:
        from adapters.registry import all_names
        return [n.split(".", 1)[1] for n in all_names() if n.startswith("notifications.")]
    except Exception:
        return []
