from ..registry import get
from typing import Dict, Any, List

def get_adapter(name: str):
    AdapterClass = get(name)
    if AdapterClass is None:
        raise ValueError(f"Flight adapter '{name}' not found")
    return AdapterClass()

def search_flights(adapter_name: str, **kwargs) -> Dict[str, Any]:
    adapter = get_adapter(adapter_name)
    return adapter.search(**kwargs)

def price_flight(adapter_name: str, offer_id: str) -> Dict[str, Any]:
    adapter = get_adapter(adapter_name)
    return adapter.price(offer_id=offer_id)

def book_flight(adapter_name: str, offer_id: str, passengers: List[Dict[str, Any]], contact: Dict[str, Any]) -> Dict[str, Any]:
    adapter = get_adapter(adapter_name)
    return adapter.book(offer_id=offer_id, passengers=passengers, contact=contact)

def get_pnr(adapter_name: str, locator: str, last_name: str) -> Dict[str, Any]:
    adapter = get_adapter(adapter_name)
    return adapter.get_pnr(locator=locator, last_name=last_name)
