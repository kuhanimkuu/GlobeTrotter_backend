import time
import logging
from typing import Any, Dict, List, Optional
import requests

from ..registry import register
from ..base import FlightsAdapter

logger = logging.getLogger(__name__)

@register("flights.duffel")
class DuffelAdapter(FlightsAdapter):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self.token = self.config.get("access_token")
        self.base = self.config.get("base_url", "https://api.duffel.com")
        if not self.token:
            logger.debug("DuffelAdapter created without access_token")

    def _headers(self):
        if not self.token:
            raise RuntimeError("Duffel access_token not configured")
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def search(self, *, origin: str, destination: str, depart_date: str,
               return_date: Optional[str] = None, adults: int = 1, cabin: str = "economy") -> Dict[str, Any]:
        
        url = f"{self.base}/air/offer_requests"
        headers = self._headers()
        payload = {
            "slices": [{"origin": origin, "destination": destination, "departure_date": depart_date}],
            "passengers": [{"type": "adt", "id": "p1"} for _ in range(adults)],
            "cabin_class": cabin.upper()
        }
        if return_date:
            payload["slices"].append({"origin": destination, "destination": origin, "departure_date": return_date})

        r = requests.post(url, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        offers = []
        for idx, offer in enumerate(data.get("data", [])):
            offers.append({
                "offer_id": offer.get("id") or f"duf_{idx}",
                "price": {"total": offer.get("total_amount"), "currency": offer.get("total_currency")},
                "raw": offer
            })
        return {"offers": offers, "raw": data}

    def price(self, *, offer_id: str) -> Dict[str, Any]:
        url = f"{self.base}/air/offers/{offer_id}"
        headers = self._headers()
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        price = {"total": data.get("data", {}).get("total_amount"), "currency": data.get("data", {}).get("total_currency")}
        return {"offer_id": offer_id, "priced": True, "price": price, "raw": data}

    def book(self, *, offer_id: str, passengers: List[Dict[str, Any]], contact: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base}/air/bookings"
        headers = self._headers()
        payload = {
            "data": {
                "offer_id": offer_id,
                "passengers": passengers,
                "contact": contact
            }
        }
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
        locator = data.get("data", {}).get("id") or f"DUF-{int(time.time())}"
        status = data.get("data", {}).get("status", "unknown")
        return {"locator": locator, "status": status, "raw": data}

    def get_pnr(self, *, locator: str, last_name: str) -> Dict[str, Any]:
        url = f"{self.base}/air/bookings/{locator}"
        headers = self._headers()
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 404:
            return {"locator": locator, "status": "NOT_FOUND", "raw": r.text}
        r.raise_for_status()
        data = r.json()
        return {"locator": locator, "status": data.get("data", {}).get("status", "unknown"), "itinerary": data.get("data", {}), "raw": data}
