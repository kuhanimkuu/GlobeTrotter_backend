import logging
from typing import Any, Dict, List, Optional, Tuple
import requests
import urllib.parse

from ..registry import register
from ..base import MapsAdapter

logger = logging.getLogger(__name__)

@register("maps.mapbox")
class MapboxAdapter(MapsAdapter):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config or {})
        self.token = self.config.get("access_token")
        self.style = self.config.get("style", "streets-v11")
        self.base_geocode = "https://api.mapbox.com/geocoding/v5/mapbox.places"
        self.base_static = "https://api.mapbox.com/styles/v1/mapbox"

    def _require_token(self):
        if not self.token:
            raise RuntimeError("Mapbox access_token not configured (maps.mapbox.access_token)")

    def geocode(self, *, query: str) -> Dict[str, Any]:
        self._require_token()
        url = f"{self.base_geocode}/{urllib.parse.quote(query)}.json"
        params = {"access_token": self.token, "limit": 5}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        results = []
        for f in data.get("features", []):
            center = f.get("center", [None, None])
            results.append({
                "place_name": f.get("place_name"),
                "lat": center[1],
                "lng": center[0],
                "id": f.get("id"),
                "raw": f,
            })
        return {"results": results, "raw": data}

    def reverse_geocode(self, *, lat: float, lng: float) -> Dict[str, Any]:
        self._require_token()
        coord = f"{lng},{lat}"
        url = f"{self.base_geocode}/{coord}.json"
        params = {"access_token": self.token, "limit": 1}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        place = data.get("features", [{}])[0] if data.get("features") else {}
        return {"place_name": place.get("place_name"), "lat": lat, "lng": lng, "raw": data}

    def places(self, *, query: str, lat: Optional[float] = None, lng: Optional[float] = None) -> Dict[str, Any]:
        self._require_token()
        url = f"{self.base_geocode}/{urllib.parse.quote(query)}.json"
        params = {"access_token": self.token, "limit": 10}
        if lat is not None and lng is not None:
            params["proximity"] = f"{lng},{lat}"
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        places = []
        for f in data.get("features", []):
            center = f.get("center", [None, None])
            places.append({
                "name": f.get("text"),
                "place_name": f.get("place_name"),
                "lat": center[1],
                "lng": center[0],
                "raw": f,
            })
        return {"places": places, "raw": data}

    def distance_matrix(self, *, origins: List[str], destinations: List[str], mode: str = "driving") -> Dict[str, Any]:
        self._require_token()
        coords = ";".join(origins + destinations)
        url = f"https://api.mapbox.com/directions-matrix/v1/mapbox/{mode}/{coords}"
        params = {"access_token": self.token, "annotations": "duration,distance"}
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        return {"rows": data.get("durations"), "raw": data}

    def static_map_url(self, *, lat: float, lng: float, zoom: int = 12, width: int = 600, height: int = 400) -> str:
        self._require_token()
        return f"{self.base_static}/{self.style}/static/{lng},{lat},{zoom}/{width}x{height}?access_token={self.token}"
