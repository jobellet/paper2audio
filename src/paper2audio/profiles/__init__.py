"""Journal profile registry.

Every module in this package is imported automatically, so adding a journal is
just: create `profiles/myjournal.py`, subclass `JournalProfile`, decorate with
`@register`.
"""

from __future__ import annotations

import importlib
import pkgutil

from ..models import Document
from .base import JournalProfile

_REGISTRY: dict[str, type[JournalProfile]] = {}


def register(cls: type[JournalProfile]) -> type[JournalProfile]:
    if cls.name in _REGISTRY and _REGISTRY[cls.name] is not cls:
        raise ValueError(f"duplicate profile name {cls.name!r}")
    _REGISTRY[cls.name] = cls
    return cls


def _load_all() -> None:
    for mod in pkgutil.iter_modules(__path__):
        if mod.name != "base" and not mod.name.startswith("_"):
            importlib.import_module(f"{__name__}.{mod.name}")


def available() -> dict[str, type[JournalProfile]]:
    _load_all()
    return dict(sorted(_REGISTRY.items()))


def get(name: str, **options) -> JournalProfile:
    profiles = available()
    if name not in profiles:
        raise KeyError(f"unknown profile {name!r}; choose from {', '.join(profiles)}")
    return profiles[name](**options)


def detect(doc: Document) -> tuple[JournalProfile, float, dict[str, float]]:
    """Return the best-matching profile, its score, and all scores."""
    scores = {name: cls.detect(doc) for name, cls in available().items()}
    best = max(scores, key=lambda n: (scores[n], n != "generic"))
    if scores[best] <= 0:
        best = "generic"
    return _REGISTRY[best](), scores[best], scores


__all__ = ["JournalProfile", "register", "available", "get", "detect"]
