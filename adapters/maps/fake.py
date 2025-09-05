from typing import Any, Dict, List, Optional
from ..registry import register
from ..base import MapsAdapter

@register("maps.fake")
class FakeMapsAdapter(MapsAdapter):
    def geocode(self, *, query: str) -> Dict[str, Any]:
        return {"results": [{"formatted_address": f"Fake Place for {query}", "lat": -1.2921, "lng": 36.8219, "place_id": "fake1"}], "raw": {}}

    def reverse_geocode(self, *, lat: float, lng: float) -> Dict[str, Any]:
        return {"address": "Fake Address", "lat": lat, "lng": lng, "raw": {}}

    def places(self, *, query: str, lat: Optional[float] = None, lng: Optional[float] = None) -> Dict[str, Any]:
        return {"places": [{"name": f"{query} Place", "lat": lat or -1.3, "lng": lng or 36.8}], "raw": {}}

    def distance_matrix(self, *, origins: List[str], destinations: List[str], mode: str = "driving") -> Dict[str, Any]:
        return {"rows": [{"elements": [{"distance": {"text": "10 km"}, "duration": {"text": "15 mins"}}]}], "raw": {}}

    def static_map_url(self, *, lat: float, lng: float, zoom: int = 12, width: int = 600, height: int = 400) -> str:
        return f"https://example.com/staticmap/{lat}/{lng}/{zoom}/{width}x{height}.png"
