#!/usr/bin/env -S /opt/homebrew/bin/uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
# <swiftbar.title>Pollenkoll</swiftbar.title>
# <swiftbar.author>nikteg</swiftbar.author>
# <swiftbar.author.github>nikteg</swiftbar.author.github>
# <swiftbar.desc>Pollen levels for a Swedish city</swiftbar.desc>
# <swiftbar.dependencies>uv</swiftbar.dependencies>
"""Pollen levels for a Swedish city.

Shows
    Menu bar: the pollens named in ``highlight``, as a percentage of the
    Swedish 7-point scale. Falls back to the single worst pollen of the day
    when none of the highlighted ones are reported.
    Dropdown: every pollen reported for the city, worst first.

Configure
    Edit the call at the bottom of this file.
      city       Must match Pollenkoll's spelling, e.g. "Göteborg".
      highlight  Pollen keys to promote to the menu bar; see NAMES below.

Source
    pollenkoll.se's WordPress JSON API, the same endpoint their Android app
    uses. SECRET is that app's embedded key, not a personal credential; the
    endpoint rejects requests without it.

Refresh
    Hourly, from the ``1h`` in this file's name. Rename to change it.
"""

import urllib.parse
from datetime import date

from swiftbar.http import get_json
from swiftbar.output import Menu
from swiftbar.plugin import run as run_plugin

SECRET = "350ed0ac-3e4e-44d3-8475-4000d27de94b"
BASE_URL = "https://pollenkoll.se/wp-json/pollenkoll-pollencounts/history"

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


def percentage(level: float) -> str:
    return f"{round(max(0, min(MAX_LEVEL, level)) / MAX_LEVEL * 100)}%"


def label(key: str, level: float) -> str:
    return f"{NAMES.get(key, key)} {percentage(level)}"


def fetch(city: str) -> list[dict]:
    query = urllib.parse.urlencode(
        {"city": city, "secret": SECRET, "platform": "android", "version": 3}
    )
    body = get_json(f"{BASE_URL}/{date.today().isoformat()}/?{query}")

    return body if isinstance(body, list) else []


def run(city: str = "Göteborg", highlight: tuple[str, ...] = ("bjork",)) -> int:
    def build(menu: Menu) -> None:
        match = next((c for c in fetch(city) if c.get("city") == city), None)

        if match is None:
            menu.unavailable(
                f"🌿 {city} unavailable", f"No pollen data for {city} today"
            )

            return

        values = sorted(match.get("values", []), key=lambda v: -v.get("level", 0))
        shown = [v for v in values if v.get("type") in highlight] or values[:1]

        for value in shown:
            menu.title("🌿 {}".format(label(value["type"], value["level"])))

        if not shown:
            menu.title("🌿 Pollen")

        menu.sep()

        for value in values:
            menu.item(label(value["type"], value["level"]))

    return run_plugin(build, name="Pollen", icon="🌿")


if __name__ == "__main__":
    raise SystemExit(run(city="Göteborg", highlight=("bjork",)))
