import time
import logging
from typing import Any, Dict, List, Optional
import requests

from ..registry import register
from ..base import FlightsAdapter

logger = logging.getLogger(__name__)

@register("flights.amadeus")
class AmadeusAdapter(FlightsAdapter):

    _TOKEN_CACHE: Dict[str, Any] = {}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self.client_id = self.config.get("client_id")
        self.client_secret = self.config.get("client_secret")
        self.env = self.config.get("environment", "test")
        self.token_ttl = int(self.config.get("token_ttl_seconds", 300))
        self.base = "https://test.api.amadeus.com" if self.env == "test" else "https://api.amadeus.com"

    # ---- auth ----
    def _get_token(self) -> str:
        cache = self._TOKEN_CACHE.get("amadeus_token")
        if cache and cache.get("expires_at", 0) > time.time():
            return cache["access_token"]

        if not self.client_id or not self.client_secret:
            raise RuntimeError("Amadeus credentials not configured")

        url = f"{self.base}/v1/security/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        r = requests.post(url, data=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        expires_in = int(data.get("expires_in", self.token_ttl))
        token = data["access_token"]
        self._TOKEN_CACHE["amadeus_token"] = {"access_token": token, "expires_at": time.time() + expires_in - 10}
        return token

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"}

    # ---- flights contract ----
    def search(self, *, origin: str, destination: str, depart_date: str,
               return_date: Optional[str] = None, adults: int = 1, cabin: str = "ECONOMY") -> Dict[str, Any]:
        """
        Returns a normalized dict: { 'offers': [ { offer_id, price: {total,currency}, segments: [...] }, ... ] }
        Note: this adapter uses Amadeus Flight Offers Search v2; adapt params as needed.
        """
        url = f"{self.base}/v2/shopping/flight-offers"
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": depart_date,
            "adults": adults,
            "travelClass": cabin,
            "max": 10
        }
        if return_date:
            params["returnDate"] = return_date

        headers = self._auth_headers()
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()

        # Normalize results into a small offers list
        offers = []
        for idx, item in enumerate(data.get("data", [])[:10]):
            price = item.get("price", {})
            offers.append({
                "offer_id": item.get("id") or f"am_offer_{idx}",
                "price": {"total": price.get("total"), "currency": price.get("currency")},
                "raw": item
            })
        return {"offers": offers, "raw": data}

    def price(self, *, offer_id: str) -> Dict[str, Any]:
       
        url = f"{self.base}/v1/booking/flight-offers/pricing"
        headers = self._auth_headers()
     
        payload = {"data": {"type": "flight-offer", "id": offer_id}}
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
     
        price = {}
        try:
            price = {"total": data.get("data", {}).get("price", {}).get("total"), "currency": data.get("data", {}).get("price", {}).get("currency")}
        except Exception:
            price = {"total": None, "currency": None}
        return {"offer_id": offer_id, "priced": True, "price": price, "raw": data}

    def book(self, *, offer_id: str, passengers: List[Dict[str, Any]], contact: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base}/v1/booking/flight-orders"
        headers = self._auth_headers()
        payload = {
            "data": {
                "type": "flight-order",
                "flightOffers": [{"id": offer_id}],
                "travelers": passengers,
                "contact": contact
            }
        }
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
        locator = data.get("data", {}).get("id") or data.get("meta", {}).get("pnr") or f"AM-{int(time.time())}"
        return {"locator": locator, "status": "CONFIRMED", "raw": data}

    def get_pnr(self, *, locator: str, last_name: str) -> Dict[str, Any]:
        url = f"{self.base}/v1/booking/flight-orders/{locator}"
        headers = self._auth_headers()
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 404:
            return {"locator": locator, "status": "NOT_FOUND", "raw": r.text}
        r.raise_for_status()
        data = r.json()
        return {"locator": locator, "status": "CONFIRMED", "itinerary": data.get("data", {}), "raw": data}
