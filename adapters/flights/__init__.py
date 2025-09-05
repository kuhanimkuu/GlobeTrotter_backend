from importlib import import_module
import logging
from typing import List

logger = logging.getLogger(__name__)

_MODULES = (
    "globetrotter.adapters.flights.amadeus",
    "globetrotter.adapters.flights.duffel",
    "globetrotter.adapters.flights.fake",  # test adapter
)

for mod in _MODULES:
    try:
        import_module(mod)
    except Exception as exc:
       
        logger.debug("Could not import flights adapter %s: %s", mod, exc)


def available_flights_adapters() -> List[str]:
    try:
        from ..registry import all_names
        return [n.split(".", 1)[1] for n in all_names() if n.startswith("flights.")]
    except Exception:
        return []
