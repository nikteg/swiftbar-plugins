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

from sources import pollenkoll
from swiftbar_lib.output import render
from swiftbar_lib.plugin import guard
from swiftbar_lib.ui import Item, Title

if __name__ == "__main__":
    guard(name="Pollen", icon="🌿")

    city = "Göteborg"
    highlight = ("bjork",)

    levels = pollenkoll.levels(city)
    # Fall back to the worst pollen of the day when none are highlighted.
    featured = [pollen for pollen in levels if pollen.key in highlight] or levels[:1]

    print(
        render(
            [
                [Title(f"🌿 {pollen.label}") for pollen in featured]
                or Title(f"🌿 {city} unavailable"),
                [Item(pollen.label) for pollen in levels]
                or Item(f"No pollen data for {city} today"),
            ]
        )
    )
