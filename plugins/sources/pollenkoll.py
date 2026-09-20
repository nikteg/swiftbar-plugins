"""Pollen counts from pollenkoll.se."""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from datetime import date

from swiftbar.http import get_json

# Public API key embedded in the Pollenkoll Android client, not a personal
# credential. The endpoint rejects requests without it.
SECRET = "350ed0ac-3e4e-44d3-8475-4000d27de94b"
BASE_URL = "https://pollenkoll.se/wp-json/pollenkoll-pollencounts/history"

#: The Swedish scale runs 0-7.
MAX_LEVEL = 7

NAMES = {
    "al": "Al",
    "alm": "Alm",
    "ambrosia": "Ambrosia",
    "bjork": "Björk",
    "bok": "Bok",
    "ek": "Ek",
    "grabo": "Gråbo",
    "gras": "Gräs",
    "hassel": "Hassel",
    "salg_vide": "Sälg/Vide",
}


@dataclass(frozen=True)
class Pollen:
    key: str
    level: float

    @property
    def label(self) -> str:
        percent = round(max(0, min(MAX_LEVEL, self.level)) / MAX_LEVEL * 100)

        return f"{NAMES.get(self.key, self.key)} {percent}%"


def levels(city: str) -> list[Pollen] | None:
    """Today's pollen for a city, worst first, or None when it is not reported."""
    query = urllib.parse.urlencode(
        {"city": city, "secret": SECRET, "platform": "android", "version": 3}
    )
    body = get_json(f"{BASE_URL}/{date.today().isoformat()}/?{query}")
    cities = body if isinstance(body, list) else []
    match = next((c for c in cities if c.get("city") == city), None)

    if match is None:
        return None

    found = [
        Pollen(value["type"], value.get("level", 0))
        for value in match.get("values", [])
        if value.get("type")
    ]

    return sorted(found, key=lambda pollen: -pollen.level)
