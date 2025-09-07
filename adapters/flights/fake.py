from typing import Any, Dict, List, Optional
from ..registry import register
from ..base import FlightsAdapter

@register("flights.fake")
class FakeFlightsAdapter(FlightsAdapter):
    def search(self, *, origin: str, destination: str, depart_date: str,
               return_date: Optional[str] = None, adults: int = 1, cabin: str = "ECONOMY") -> Dict[str, Any]:
        offers = [{
            "offer_id": "fake_offer_1",
            "price": {"total": "199.00", "currency": "USD"},
            "raw": {}
        }]
        return {"offers": offers, "raw": {}}

    def price(self, *, offer_id: str) -> Dict[str, Any]:
        return {
            "offer_id": offer_id,
            "priced": True,
            "price": {"total": "199.00", "currency": "USD"},
            "raw": {}
        }

    def book(self, *, offer_id: str, passengers: List[Dict[str, Any]], contact: Dict[str, Any]) -> Dict[str, Any]:
        # Fake booking always succeeds with a fixed locator
        price = {"total": "199.00", "currency": "USD"}
        return {
            "status": "CONFIRMED",
            "external_booking_id": "FAKEPNR123",
            "local_booking_id": None,
            "confirmation": {"offer_id": offer_id},
            "total_amount": price.get("total"),
            "currency": price.get("currency"),
            "passengers": passengers,
        }

    def get_pnr(self, *, locator: str, last_name: str) -> Dict[str, Any]:
        return {
            "locator": locator,
            "status": "CONFIRMED",
            "itinerary": {},
            "raw": {}
        }
