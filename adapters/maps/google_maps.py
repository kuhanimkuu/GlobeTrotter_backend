import logging
from typing import Any, Dict, List, Optional, Tuple
import requests

from ..registry import register
from ..base import MapsAdapter

logger = logging.getLogger(__name__)

@register("maps.google")
class GoogleMapsAdapter(MapsAdapter):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self.api_key = self.config.get("api_key")
        self.base = "https://maps.googleapis.com/maps/api"

    def _require_key(self):
        if not self.api_key:
            raise RuntimeError("Google Maps API key not configured (maps.google.api_key)")

    def geocode(self, *, query: str) -> Dict[str, Any]:
        self._require_key()
        url = f"{self.base}/geocode/json"
        params = {"address": query, "key": self.api_key}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("results", []):
            loc = item.get("geometry", {}).get("location", {})
            results.append({
                "formatted_address": item.get("formatted_address"),
                "lat": loc.get("lat"),
                "lng": loc.get("lng"),
                "place_id": item.get("place_id"),
                "raw": item,
            })
        return {"results": results, "raw": data}

    def reverse_geocode(self, *, lat: float, lng: float) -> Dict[str, Any]:
        self._require_key()
        url = f"{self.base}/geocode/json"
        params = {"latlng": f"{lat},{lng}", "key": self.api_key}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        address = data.get("results", [{}])[0] if data.get("results") else {}
        return {"address": address.get("formatted_address"), "lat": lat, "lng": lng, "raw": data}

    def places(self, *, query: str, lat: Optional[float] = None, lng: Optional[float] = None) -> Dict[str, Any]:
        self._require_key()
        url = f"{self.base}/place/textsearch/json"
        params = {"query": query, "key": self.api_key}
        if lat is not None and lng is not None:
            params["location"] = f"{lat},{lng}"
            params["radius"] = 50000 
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        places = []
        for p in data.get("results", []):
            places.append({
                "name": p.get("name"),
                "address": p.get("formatted_address"),
                "place_id": p.get("place_id"),
                "lat": p.get("geometry", {}).get("location", {}).get("lat"),
                "lng": p.get("geometry", {}).get("location", {}).get("lng"),
                "raw": p,
            })
        return {"places": places, "raw": data}

    def distance_matrix(self, *, origins: List[str], destinations: List[str], mode: str = "driving") -> Dict[str, Any]:
        self._require_key()
        url = f"{self.base}/distancematrix/json"
        params = {
            "origins": "|".join(origins),
            "destinations": "|".join(destinations),
            "mode": mode,
            "key": self.api_key,
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        return {"rows": data.get("rows", []), "raw": data}

    def static_map_url(self, *, lat: float, lng: float, zoom: int = 12, width: int = 600, height: int = 400) -> str:
        
        self._require_key()
        size = f"{width}x{height}"
        markers = f"color:red|{lat},{lng}"
        return f"https://maps.googleapis.com/maps/api/staticmap?center={lat},{lng}&zoom={zoom}&size={size}&markers={markers}&key={self.api_key}"
