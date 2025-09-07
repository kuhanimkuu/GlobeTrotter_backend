# adapters/flights/__init__.py
from importlib import import_module
import logging
from typing import List
from .amadeus import AmadeusAdapter
from .duffel import DuffelAdapter
from .fake import FakeFlightsAdapter
logger = logging.getLogger(__name__)

# List of adapter modules to try importing
_MODULES = (
    "globetrotter.adapters.flights.amadeus",
    "globetrotter.adapters.flights.duffel",
    "globetrotter.adapters.flights.fake",  # test adapter
)

# Dynamically import adapters and log failures
for mod in _MODULES:
    try:
        import_module(mod)
    except Exception as exc:
        logger.warning("Could not import flights adapter %s: %s", mod, exc)


# Utility function: list all available flight adapters
def available_flights_adapters() -> List[str]:
    """
    Returns a list of available flight adapter names.
    """
    try:
        from ..registry import all_names
        return [n.split(".", 1)[1] for n in all_names() if n.startswith("flights.")]
    except Exception:
        logger.warning("Registry unavailable, returning empty flight adapter list")
        return []


# Optional: Default adapter
DEFAULT_FLIGHT_ADAPTER = "fake"

# Central search function to unify all adapters
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
  # optional

ADAPTERS = {
    "amadeus": AmadeusAdapter,
    "duffel": DuffelAdapter,
    "fake": FakeFlightsAdapter,  # good for testing
}
