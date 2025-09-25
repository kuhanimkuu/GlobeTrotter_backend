from importlib import import_module
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


_MODULES = (
    "adapters.payments.stripe",
    "adapters.payments.mpesa",
    "adapters.payments.flutterwave",
    "adapters.payments.fake", 
)

for _m in _MODULES:
    try:
        import_module(_m)
    except Exception as exc:
        logger.debug("Could not import payment adapter %s: %s", _m, exc)


def available_payment_adapters() -> List[str]:
    """
    Return a list of available payment adapters (short names).
    Example: ["stripe", "mpesa", "flutterwave", "fake"]
    """
    names = []
    for m in _MODULES:
        short = m.split(".")[-1]
        names.append(short)

    try:
        from ..registry import all_names
        for n in all_names():
            if n.startswith("payments."):
                short = n.split(".", 1)[1]
                if short not in names:
                    names.append(short)
    except Exception:
        pass

    return sorted(names)


def get_payment_adapter(
    name: str, 
    config: Optional[Dict[str, Any]] = None, 
    *, 
    use_registry: bool = True
):
   
    name = name.lower()

    if use_registry:
        try:
            from .. import get_payment_adapter as _top_get
            return _top_get(name)
        except Exception:
            logger.debug("Global adapters.get_payment_adapter not available or failed for %s; falling back", name)

    module_path = f"globetrotter.adapters.payments.{name}"
    try:
        mod = import_module(module_path)
    except Exception as exc:
        raise ImportError(f"Payment adapter module not found: {module_path} ({exc})") from exc

    AdapterCls = None
    for attr in dir(mod):
        if attr.lower().endswith("adapter"):
            candidate = getattr(mod, attr)
            if isinstance(candidate, type):
                AdapterCls = candidate
                break

    if AdapterCls is None:
        raise ImportError(f"No Adapter class found in {module_path}. Expected a class like 'StripeAdapter'.")

    try:
        inst = AdapterCls(config or {})
    except TypeError:
        try:
            inst = AdapterCls()
        except Exception as exc:
            raise RuntimeError(f"Failed to instantiate adapter {AdapterCls} from {module_path}: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to instantiate adapter {AdapterCls} from {module_path}: {exc}") from exc

    return inst
