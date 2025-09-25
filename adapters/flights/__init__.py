from importlib import import_module
import logging
from typing import List
from .amadeus import AmadeusAdapter
from .duffel import DuffelAdapter
from .fake import FakeFlightsAdapter
from ..registry import get as get_adapter_registry
logger = logging.getLogger(__name__)

_MODULES = (
    "adapters.flights.amadeus",
    "adapters.flights.duffel",
    "adapters.flights.fake", 
)


for mod in _MODULES:
    try:
        import_module(mod)
    except Exception as exc:
        logger.warning("Could not import flights adapter %s: %s", mod, exc)


def available_flights_adapters() -> List[str]:
  
    try:
        from adapters.registry import all_names
        return [n.split(".", 1)[1] for n in all_names() if n.startswith("flights.")]
    except Exception:
        logger.warning("Registry unavailable, returning empty flight adapter list")
        return []


DEFAULT_FLIGHT_ADAPTER = "amadeus"

def search_flights(origin: str, destination: str, provider: str = None):
    provider = provider or DEFAULT_FLIGHT_ADAPTER
    if provider == "amadeus":
        from .amadeus import search_flights as search
    elif provider == "duffel":
        from .duffel import search_flights as search
    elif provider == "fake":
        from .fake import search_flights as search
    else:
        raise ValueError(f"Unknown flight provider: {provider}")

    return search(origin, destination)


ADAPTERS = {
    "amadeus": AmadeusAdapter,
    "duffel": DuffelAdapter,
    "fake": FakeFlightsAdapter,  
}
def get_flight_adapter(name: str):
    if "." not in name:
        name = f"flights.{name.lower()}"
    try:
        AdapterClass = get_adapter_registry(name)
        return AdapterClass()
    except KeyError:
        raise ImportError(f"Flight provider '{name}' is not supported")