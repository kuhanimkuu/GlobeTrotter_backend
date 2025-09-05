from typing import Dict, Type
from .base import AdapterBase

_REGISTRY: Dict[str, Type[AdapterBase]] = {}

def register(name: str):
    name = name.lower()
    if "." not in name:
        raise ValueError("Adapter name must be namespaced, e.g. 'payments.stripe'")
    def _decorator(cls: Type[AdapterBase]):
        _REGISTRY[name] = cls
        return cls
    return _decorator

def get(name: str):
    cls = _REGISTRY.get(name.lower())
    if not cls:
        raise KeyError(f"Unknown adapter: {name}")
    return cls

def all_names():
    return sorted(_REGISTRY.keys())
