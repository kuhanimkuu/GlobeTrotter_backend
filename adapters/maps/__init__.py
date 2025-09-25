from importlib import import_module
import logging
from typing import List
from ..registry import get as get_adapter_registry
from typing import Any
logger = logging.getLogger(__name__)

_MODULES = (
    "adapters.maps.google_maps",
    "adapters.maps.mapbox",
    "adapters.maps.fake",
)

for mod in _MODULES:
    try:
        import_module(mod)
    except Exception as exc:
        logger.debug("Could not import maps adapter %s: %s", mod, exc)


def available_maps_adapters() -> List[str]:
    try:
        from ..registry import all_names
        return [n.split(".", 1)[1] for n in all_names() if n.startswith("maps.")]
    except Exception:
        return []


def get_maps_adapter(name: str) -> Any:
    adapter_cls = get_adapter_registry(f"maps.{name}")
    if not adapter_cls:
        raise ImportError(f"Maps adapter '{name}' not found")
    return adapter_cls()
