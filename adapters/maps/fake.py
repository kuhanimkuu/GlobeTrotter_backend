from typing import Any, Dict, List, Optional
from ..registry import register
from ..base import MapsAdapter

@register("maps.fake")
class FakeMapsAdapter(MapsAdapter):
    AIRPORTS = {
        # Africa
        "NBO": ("Nairobi", "Kenya"),
        "LOS": ("Lagos", "Nigeria"),
        "CPT": ("Cape Town", "South Africa"),
        "JNB": ("Johannesburg", "South Africa"),
        "ADD": ("Addis Ababa", "Ethiopia"),
        "DXB": ("Dubai", "United Arab Emirates"),
        "DOH": ("Doha", "Qatar"),

        # USA
        "LAX": ("Los Angeles", "United States"),
        "SFO": ("San Francisco", "United States"),
        "ORD": ("Chicago", "United States"),
        "ATL": ("Atlanta", "United States"),
        "SEA": ("Seattle", "United States"),

        # Europe
        "CDG": ("Paris", "France"),
        "LHR": ("London", "United Kingdom"),
        "FRA": ("Frankfurt", "Germany"),
        "MAD": ("Madrid", "Spain"),
        "BCN": ("Barcelona", "Spain"),
        "IST": ("Istanbul", "Turkey"),

        # Asia-Pacific
        "HND": ("Tokyo", "Japan"),
        "NRT": ("Tokyo", "Japan"),
        "ICN": ("Seoul", "South Korea"),
        "SYD": ("Sydney", "Australia"),
        "MEL": ("Melbourne", "Australia"),
        "AKL": ("Auckland", "New Zealand"),
    }

    # City - Country
    CITIES = {
        "NAIROBI": "Kenya",
        "LAGOS": "Nigeria",
        "CAPE TOWN": "South Africa",
        "JOHANNESBURG": "South Africa",
        "ADDIS ABABA": "Ethiopia",
        "DUBAI": "United Arab Emirates",
        "DOHA": "Qatar",

        "LOS ANGELES": "United States",
        "SAN FRANCISCO": "United States",
        "CHICAGO": "United States",
        "ATLANTA": "United States",
        "SEATTLE": "United States",

        "PARIS": "France",
        "LONDON": "United Kingdom",
        "FRANKFURT": "Germany",
        "MADRID": "Spain",
        "BARCELONA": "Spain",
        "ISTANBUL": "Turkey",

        "TOKYO": "Japan",
        "SEOUL": "South Korea",
        "SYDNEY": "Australia",
        "MELBOURNE": "Australia",
        "AUCKLAND": "New Zealand",
    }

    def geocode(self, *, query: str) -> Dict[str, Any]:
        code = query.upper().strip()
        if code in self.AIRPORTS:
            city, country = self.AIRPORTS[code]
        else:
            city = query.title()
            country = self.CITIES.get(code, "Unknown Country")

        formatted = f"{city}, {country}"

        return {
            "results": [{
                "formatted_address": formatted,
                "city": city,
                "country": country,
                "lat": -1.2921,  
                "lng": 36.8219,
                "place_id": f"fake-{code}",
            }],
            "raw": {}
        }

    def get_airports_by_country(self, country_name: str) -> List[str]:
        """
        Return a list of airport codes for a given country.
        """
        country_upper = country_name.upper()
        airports = [code for code, (_, country) in self.AIRPORTS.items() if country.upper() == country_upper]
        return airports or []

    def reverse_geocode(self, *, lat: float, lng: float) -> Dict[str, Any]:
        return {
            "address": "Fake Address",
            "lat": lat,
            "lng": lng,
            "raw": {}
        }
    

    def places(self, *, query: str, lat: Optional[float] = None, lng: Optional[float] = None) -> Dict[str, Any]:
        return {
            "places": [{
                "name": f"{query} Place",
                "lat": lat or -1.3,
                "lng": lng or 36.8
            }],
            "raw": {}
        }

    def distance_matrix(self, *, origins: List[str], destinations: List[str], mode: str = "driving") -> Dict[str, Any]:
        return {
            "rows": [{
                "elements": [{
                    "distance": {"text": "10 km"},
                    "duration": {"text": "15 mins"}
                }]
            }],
            "raw": {}
        }

    def static_map_url(self, *, lat: float, lng: float, zoom: int = 12, width: int = 600, height: int = 400) -> str:
        return f"https://example.com/staticmap/{lat}/{lng}/{zoom}/{width}x{height}.png"

    def get_country_from_result(self, result: Dict[str, Any]) -> Optional[str]:
        return result.get("country", "Unknown Country")
