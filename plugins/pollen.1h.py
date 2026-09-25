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
    The city is ``city`` in ~/.config/swiftbar-plugins/pollen.json, outside
    the repo. It must match Pollenkoll's spelling, e.g. {"city": "Malmö"}.
    Until it is set the dropdown says so above rows of —, and nothing is
    fetched.
    Which pollens show is the menu at the bottom of this file. Every pollen
    is one row, so reordering, renaming or dropping one is a line.

Source
    pollenkoll.se's WordPress JSON API, the same endpoint their Android app
    uses. SECRET is that app's embedded key, not a personal credential; the
    endpoint rejects requests without it.

Refresh
    Hourly, from the ``1h`` in this file's name. Rename to change it.
"""

import urllib.parse
from collections import defaultdict
from datetime import date

from swiftbar_lib import config
from swiftbar_lib.components import Unconfigured
from swiftbar_lib.data import string_at
from swiftbar_lib.http import get_json
from swiftbar_lib.output import show
from swiftbar_lib.ui import Item, Title

# Public API key embedded in the Pollenkoll Android client, not a personal
# credential. The endpoint rejects requests without it.
SECRET = "350ed0ac-3e4e-44d3-8475-4000d27de94b"
BASE_URL = "https://pollenkoll.se/wp-json/pollenkoll-pollencounts/history"

#: The Swedish scale runs 0-7.
MAX_LEVEL = 7

#: What a pollen with no reading shows.
UNKNOWN = "—"


def levels(city: str) -> dict[str, str]:
    """Today's readings as pollen key -> percentage, defaulting to UNKNOWN."""
    query = urllib.parse.urlencode(
        {"city": city, "secret": SECRET, "platform": "android", "version": 3}
    )
    body = get_json(f"{BASE_URL}/{date.today().isoformat()}/?{query}")
    cities = body if isinstance(body, list) else []
    today = next((c for c in cities if c.get("city") == city), None)

    readings = defaultdict(lambda: UNKNOWN)

    for value in (today or {}).get("values", []):
        level = max(0, min(MAX_LEVEL, value.get("level", 0)))
        readings[value["type"]] = f"{round(level / MAX_LEVEL * 100)}%"

    return readings


if __name__ == "__main__":
    city = string_at(config.load(__file__), "city")
    today = levels(city) if city else defaultdict(lambda: UNKNOWN)

    show(
        Title(f"🌿 Björk {today['bjork']}"),
        Unconfigured(__file__, "city") if not city else None,
        Item(f"Al {today['al']}"),
        Item(f"Alm {today['alm']}"),
        Item(f"Ambrosia {today['ambrosia']}"),
        Item(f"Björk {today['bjork']}"),
        Item(f"Bok {today['bok']}"),
        Item(f"Ek {today['ek']}"),
        Item(f"Gråbo {today['grabo']}"),
        Item(f"Gräs {today['gras']}"),
        Item(f"Hassel {today['hassel']}"),
        Item(f"Sälg/Vide {today['salg_vide']}"),
    )
