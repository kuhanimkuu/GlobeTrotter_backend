from importlib import import_module
from typing import Any, Dict
from django.conf import settings
from .registry import get as _get_cls, all_names as _all_names
from .base import (
    PaymentAdapter, SmsAdapter, EmailAdapter, PushAdapter, FlightsAdapter, MapsAdapter
)


_MODULES = (
    # Payments
    "globetrotter.adapters.payments.stripe",
    "globetrotter.adapters.payments.mpesa",
    "globetrotter.adapters.payments.flutterwave",
    # Notifications
    "globetrotter.adapters.notifications.sms_twilio",
    "globetrotter.adapters.notifications.email_sendgrid",
    "globetrotter.adapters.notifications.push_fcm",
    # Flights
    "globetrotter.adapters.flights.amadeus",
    "globetrotter.adapters.flights.duffel",
    # Maps
    "globetrotter.adapters.maps.google_maps",
    "globetrotter.adapters.maps.mapbox",
)

for _m in _MODULES:
    try:
        import_module(_m)
    except Exception:
        pass


def _cfg(name: str) -> Dict[str, Any]:
    return getattr(settings, "ADAPTERS_CONFIG", {}).get(name.lower(), {})


# --- Payment ---
def get_payment_adapter(name: str) -> PaymentAdapter:
    return _get_cls(f"payments.{name}")(_cfg(f"payments.{name}"))


# --- Notifications ---
def get_sms_adapter(name: str) -> SmsAdapter:
    return _get_cls(f"notifications.{name}")(_cfg(f"notifications.{name}"))


def get_email_adapter(name: str) -> EmailAdapter:
    return _get_cls(f"notifications.{name}")(_cfg(f"notifications.{name}"))


def get_push_adapter(name: str) -> PushAdapter:
    return _get_cls(f"notifications.{name}")(_cfg(f"notifications.{name}"))


# --- Flights ---
def get_flights_adapter(name: str) -> FlightsAdapter:
    return _get_cls(f"flights.{name}")(_cfg(f"flights.{name}"))


# --- Maps ---
def get_maps_adapter(name: str) -> MapsAdapter:
    return _get_cls(f"maps.{name}")(_cfg(f"maps.{name}"))


def available_adapters() -> list[str]:
    return _all_names()
