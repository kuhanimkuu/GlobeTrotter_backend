import time
import logging
import token
from typing import Any, Dict, List, Optional
import requests

from ..registry import register
from ..base import FlightsAdapter

logger = logging.getLogger(__name__)

AIRLINE_INFO = {
    "AA": {"name": "American Airlines", "logo": "https://content.airhex.com/content/logos/airlines_AA_200_200.png"},
    "UA": {"name": "United Airlines", "logo": "https://content.airhex.com/content/logos/airlines_UA_200_200.png"},
    "BA": {"name": "British Airways", "logo": "https://content.airhex.com/content/logos/airlines_BA_200_200.png"},
    "KL": {"name": "KLM Royal Dutch Airlines", "logo": "https://content.airhex.com/content/logos/airlines_KL_200_200.png"},
    "AF": {"name": "Air France", "logo": "https://content.airhex.com/content/logos/airlines_AF_200_200.png"},
    "LH": {"name": "Lufthansa", "logo": "https://content.airhex.com/content/logos/airlines_LH_200_200.png"},
    "EK": {"name": "Emirates", "logo": "https://content.airhex.com/content/logos/airlines_EK_200_200.png"},
    "QR": {"name": "Qatar Airways", "logo": "https://content.airhex.com/content/logos/airlines_QR_200_200.png"},
    "ET": {"name": "Ethiopian Airlines", "logo": "https://content.airhex.com/content/logos/airlines_ET_200_200.png"},
    "KQ": {"name": "Kenya Airways", "logo": "https://content.airhex.com/content/logos/airlines_KQ_200_200.png"},
}

def get_airline_info(code: str) -> Dict[str, str]:
    return AIRLINE_INFO.get(code, {
        "name": code,
        "logo": f"https://content.airhex.com/content/logos/airlines_{code}_200_200.png"
    })


@register("flights.amadeus")
class AmadeusAdapter(FlightsAdapter):
    _TOKEN_CACHE: Dict[str, Any] = {}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self.client_id = self.config.get("client_id")
        self.client_secret = self.config.get("client_secret")
        self.env = (self.config.get("environment") or "test").lower().strip()
        self.token_ttl = int(self.config.get("token_ttl_seconds", 300))

       
        self.base = (
            "https://test.api.amadeus.com"
        if self.env == "test"
        else "https://api.amadeus.com"
        )
        if not self.client_id or not self.client_secret:
            raise ValueError("[AmadeusAdapter] Missing client_id or client_secret")
        logger.info(f"[AmadeusAdapter] Using env='{self.env}', base='{self.base}'")

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
        "client_secret": self.client_secret,
        }

        r = requests.post(url, data=payload, timeout=10)
        if r.status_code != 200:
            logger.error(
            "[AmadeusAdapter] Failed to fetch token (%s): %s",
            r.status_code,
            r.text,
            )
            r.raise_for_status()  

        data = r.json()

        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"[AmadeusAdapter] No access_token in response: {data}")

        expires_in = int(data.get("expires_in", self.token_ttl))
        self._TOKEN_CACHE["amadeus_token"] = {
        "access_token": token,
        "expires_at": time.time() + expires_in - 10, 
        }

        return token

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }
    def search(
    self,
    *,
    origin: str,
    destination: str,
    depart_date: str,
    return_date: Optional[str] = None,
    adults: int = 1,
    cabin: str = "ECONOMY",
) -> Dict[str, Any]:
        url = f"{self.base}/v2/shopping/flight-offers"
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": depart_date,
            "adults": adults,
            "travelClass": cabin,
            "max": 10,
        }
        if return_date:
            params["returnDate"] = return_date
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        r = requests.get(url, params=params, headers=headers, timeout=15)
        logger.debug("[Amadeus] URL: %s", r.url)
        logger.debug("[Amadeus] Headers: %s", headers)
        logger.debug("[Amadeus] Status: %s", r.status_code)
        logger.debug("[Amadeus] Response: %s", r.text[:500])

        r.raise_for_status()
        data = r.json()

        offers = []
        for idx, item in enumerate(data.get("data", [])[:10]):
            try:
                price = item.get("price", {})
                itineraries = item.get("itineraries", [])
                if not itineraries:
                    logger.warning(f"No itineraries in item: {item}")
                    continue

                first_seg = itineraries[0]["segments"][0]
                last_seg = itineraries[-1]["segments"][-1]

                airline_code = first_seg["carrierCode"]
                airline_info = get_airline_info(airline_code)

                offers.append({
                    "offer_id": item.get("id") or f"am_offer_{idx}",
                    "airline": airline_info["name"],
                    "airline_logo": airline_info["logo"],
                    "flight_number": f"{airline_code}{first_seg['number']}",
                    "origin_code": first_seg["departure"]["iataCode"],
                    "destination_code": last_seg["arrival"]["iataCode"],
                    "departure_time": first_seg["departure"]["at"],
                    "arrival_time": last_seg["arrival"]["at"],
                    "duration": itineraries[0].get("duration"),
                    "price": float(price.get("total", 0)),
                    "currency": price.get("currency"),
                    "stops": len(itineraries[0].get("segments", [])) - 1,
                    "provider": "amadeus",
                    "raw": item,
                })
            except Exception as e:
                logger.warning(f"Failed to normalize offer: {e}")
        logger.debug(f"[AmadeusAdapter] Parsed {len(offers)} offers")
        return {"offers": offers, "raw": data}

    def price(self, *, offer: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base}/v1/booking/flight-offers/pricing"
        headers = self._auth_headers()
        payload = {"data": [offer]}
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()

        try:
            priced_offer = data.get("data", [])[0]
            price = priced_offer.get("price", {})
            itineraries = priced_offer.get("itineraries", [])
            first_seg = itineraries[0]["segments"][0]
            last_seg = itineraries[-1]["segments"][-1]

            airline_code = first_seg["carrierCode"]
            airline_info = get_airline_info(airline_code)

            normalized = {
                "offer_id": priced_offer.get("id"),
                "airline": airline_info["name"],
                "airline_logo": airline_info["logo"],
                "flight_number": f"{airline_code}{first_seg['number']}",
                "origin_code": first_seg["departure"]["iataCode"],
                "destination_code": last_seg["arrival"]["iataCode"],
                "departure_time": first_seg["departure"]["at"],
                "arrival_time": last_seg["arrival"]["at"],
                "duration": itineraries[0].get("duration"),
                "price": float(price.get("total", 0)),
                "currency": price.get("currency"),
                "provider": "amadeus",
            }
        except Exception:
            normalized = {}

        return {
            "offer_id": offer.get("id"),
            "priced": True,
            "normalized": normalized,
            "raw": data,
        }

    def book(
        self,
        *,
        offer: Dict[str, Any],
        passengers: List[Dict[str, Any]],
        contact: Dict[str, Any],
    ) -> Dict[str, Any]:
        url = f"{self.base}/v1/booking/flight-orders"
        headers = self._auth_headers()
        payload = {
            "data": {
                "type": "flight-order",
                "flightOffers": [offer],
                "travelers": passengers,
                "contact": contact,
            }
        }
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()

        try:
            offer_data = data.get("data", {}).get("flightOffers", [])[0]
            price_data = offer_data.get("price", {})
            itineraries = offer_data.get("itineraries", [])
            first_seg = itineraries[0]["segments"][0]
            last_seg = itineraries[-1]["segments"][-1]

            airline_code = first_seg["carrierCode"]
            airline_info = get_airline_info(airline_code)

            normalized = {
                "offer_id": offer_data.get("id"),
                "airline": airline_info["name"],
                "airline_logo": airline_info["logo"],
                "flight_number": f"{airline_code}{first_seg['number']}",
                "origin_code": first_seg["departure"]["iataCode"],
                "destination_code": last_seg["arrival"]["iataCode"],
                "departure_time": first_seg["departure"]["at"],
                "arrival_time": last_seg["arrival"]["at"],
                "duration": itineraries[0].get("duration"),
                "price": float(price_data.get("total", 0)),
                "currency": price_data.get("currency"),
                "provider": "amadeus",
            }
        except Exception:
            normalized = {}

        locator = (
            data.get("data", {}).get("id")
            or data.get("meta", {}).get("pnr")
            or f"AM-{int(time.time())}"
        )

        return {
            "status": "CONFIRMED",
            "external_booking_id": locator,
            "local_booking_id": None,
            "confirmation": data,
            "normalized": normalized,
            "passengers": passengers,
        }

    def get_pnr(self, *, locator: str, last_name: str) -> Dict[str, Any]:
        url = f"{self.base}/v1/booking/flight-orders/{locator}"
        headers = self._auth_headers()
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code == 404:
            return {"locator": locator, "status": "NOT_FOUND", "raw": r.text}

        r.raise_for_status()
        data = r.json()
        return {
            "locator": locator,
            "status": "CONFIRMED",
            "itinerary": data.get("data", {}),
            "raw": data,
        }
