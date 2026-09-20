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
from swiftbar.output import render
from swiftbar.plugin import guard
from swiftbar.ui import Item, Node, Title, Unavailable


def Pollen(city: str, highlight: tuple[str, ...]) -> Node:
    levels = pollenkoll.levels(city)

    if levels is None:
        return Unavailable(f"🌿 {city} unavailable", f"No pollen data for {city} today")

    # Fall back to the worst pollen of the day when none are highlighted.
    shown = [pollen for pollen in levels if pollen.key in highlight] or levels[:1]

    return [
        [Title(f"🌿 {pollen.label}") for pollen in shown],
        [Item(pollen.label) for pollen in levels],
    ]


if __name__ == "__main__":
    guard(name="Pollen", icon="🌿")
    print(render(Pollen(city="Göteborg", highlight=("bjork",))))
