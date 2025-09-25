from typing import Any, Dict, List, Optional
from ..registry import register
from ..base import FlightsAdapter
import random
from datetime import datetime, timedelta

@register("flights.fake")
class FakeFlightsAdapter(FlightsAdapter):
    AIRLINES = ["AirFake", "TestAir", "DemoFlights", "SampleAir"]
    CABINS = ["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"]
    AIRPORTS = ["JFK", "LHR", "CDG", "DXB", "HND", "SIN", "FRA", "AMS", "ORD", "SFO"]

    _bookings: Dict[str, Dict] = {}
    _offers_seats: Dict[str, int] = {}
    _offers: Dict[str, Dict] = {}

    def _generate_offer_id(self):
        return f"FAKE{random.randint(1000, 9999)}"

    def _generate_price(self, cabin: str, adults: int):
        base_price = random.randint(100, 500)
        multiplier = {"ECONOMY": 1, "PREMIUM_ECONOMY": 1.5, "BUSINESS": 2.5, "FIRST": 4}
        total = base_price * multiplier.get(cabin, 1) * adults
        return {"total": f"{total:.2f}", "currency": "USD"}

    def _generate_seats(self, cabin: str):
        max_seats = {"ECONOMY": 150, "PREMIUM_ECONOMY": 50, "BUSINESS": 30, "FIRST": 10}
        return random.randint(5, max_seats.get(cabin, 100))

    def search(
        self,
        *,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        adults: int = 1,
        cabin: str = "ECONOMY",
    ) -> Dict[str, Any]:
        """
        Generate ~50 fake flight offers from all over the world.
        Always include at least one Nairobi (NBO) flight.
        """
        offers = []
        airports = list(set(self.AIRPORTS + [
            "NBO", "LOS", "CPT", "DXB", "DOH", "JNB", "ADD",
            "LAX", "SFO", "ORD", "ATL", "SEA",
            "CDG", "LHR", "FRA", "MAD", "BCN", "IST",
            "HND", "NRT", "ICN", "SYD", "MEL", "AKL"
        ]))

        try:
            base_date = datetime.strptime(departure_date, "%Y-%m-%d")
        except Exception:
            base_date = datetime.utcnow()

        now_utc = datetime.utcnow()

        total_offers = 50
        for idx in range(total_offers):
            offer_cabin = random.choice(self.CABINS)
            offer_id = self._generate_offer_id()
            seats = self._generate_seats(offer_cabin)
            self._offers_seats[offer_id] = seats

            if idx == 0:
                if origin and origin.upper() == "NBO":
                    origin_code = "NBO"
                    destination_code = random.choice([a for a in airports if a != "NBO"])
                elif destination and destination.upper() == "NBO":
                    origin_code = random.choice([a for a in airports if a != "NBO"])
                    destination_code = "NBO"
                else:
                    if random.random() > 0.5:
                        origin_code = "NBO"
                        destination_code = random.choice([a for a in airports if a != "NBO"])
                    else:
                        origin_code = random.choice([a for a in airports if a != "NBO"])
                        destination_code = "NBO"
            else:
                origin_code = origin.upper() if origin else random.choice(airports)
                destination_code = destination.upper() if destination else random.choice(airports)
                while destination_code == origin_code:
                    destination_code = random.choice(airports)
            earliest = max(now_utc + timedelta(hours=1), base_date)
            latest = earliest + timedelta(days=5)
            dep_time = earliest + timedelta(
                minutes=random.randint(0, int((latest - earliest).total_seconds() / 60))
            )
            arr_time = dep_time + timedelta(
                hours=random.randint(1, 12), minutes=random.choice([0, 15, 30, 45])
            )

            price = self._generate_price(offer_cabin, adults)

            offer = {
                "id": offer_id,
                "offer_id": offer_id,
                "itineraries": [
                    {
                        "segments": [
                            {
                                "number": f"FA{random.randint(100,999)}",
                                "carrierCode": random.choice(self.AIRLINES),
                                "departure": {"iataCode": origin_code, "at": dep_time.strftime("%Y-%m-%dT%H:%M:%SZ")},
                                "arrival": {"iataCode": destination_code, "at": arr_time.strftime("%Y-%m-%dT%H:%M:%SZ")},
                            }
                        ]
                    }
                ],
                "numberOfBookableSeats": seats,
                "price": price,
                "cabin": offer_cabin,
            }

            offers.append(offer)
            self._offers[offer_id] = offer  

        return {"offers": offers, "raw": {}}

    def price(self, *, offer_id: str, adults: int = 1) -> Dict[str, Any]:
        offer = self._offers.get(offer_id)
        if not offer:
            raise ValueError("Invalid offer ID")
        return {
            "offer_id": offer_id,
            "priced": True,
            "price": offer["price"],
            "available_seats": self._offers_seats[offer_id],
            "raw": {}
        }

    def book(self, *, offer_id: str, passengers: List[Dict[str, Any]], contact: Dict[str, Any]) -> Dict[str, Any]:
        offer = self._offers.get(offer_id)
        if not offer:
            raise ValueError("Invalid offer ID")

        pnr = f"FAKEPNR{random.randint(1000,9999)}"
        booking = {
            "status": "CONFIRMED",
            "external_booking_id": pnr,
            "local_booking_id": None,
            "confirmation": {"offer_id": offer_id},
            "total_amount": offer["price"]["total"],
            "currency": offer["price"]["currency"],
            "passengers": passengers,
            "contact": contact
        }
        self._bookings[pnr] = booking
        return booking

    def get_pnr(self, *, locator: str, last_name: str) -> Dict[str, Any]:
        booking = self._bookings.get(locator)
        if not booking:
            return {"status": "NOT_FOUND"}
        return booking
