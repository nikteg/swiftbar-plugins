#!/usr/bin/env -S /opt/homebrew/bin/uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
# <swiftbar.title>Golden hour</swiftbar.title>
# <swiftbar.author>nikteg</swiftbar.author>
# <swiftbar.author.github>nikteg</swiftbar.author.github>
# <swiftbar.desc>This evening's golden hour</swiftbar.desc>
# <swiftbar.dependencies>uv</swiftbar.dependencies>
"""This evening's golden hour for a city.

Shows
    Menu bar: the evening golden hour window, e.g. 🌇 20:14 - 21:02 🌇.
    Dropdown: the resolved location, linking to the source page.

Configure
    Edit the call at the bottom of this file.
      country, city  Path segments of a meteogram.org sun page, lowercase and
                     unaccented, as in meteogram.org/sun/sweden/goteborg/.

Source
    Scraped from meteogram.org, which publishes no API. The parser reads the
    ``avond_goudenhour`` table cell and the page description, so a redesign of
    that page is what will break this plugin.

Refresh
    Hourly, from the ``1h`` in this file's name. Rename to change it.
"""

from sources import meteogram
from swiftbar.output import render
from swiftbar.plugin import guard
from swiftbar.ui import Item, Node, Title, Unavailable


def GoldenHour(country: str, city: str) -> Node:
    tonight = meteogram.evening(country, city)

    if not tonight.times:
        return Unavailable("🌇 —", f"No golden hour found for {city}", href=tonight.url)

    return [
        Title(f"🌇 {tonight.times} 🌇"),
        Item(tonight.location, href=tonight.url),
    ]


if __name__ == "__main__":
    guard(name="Golden hour", icon="🌇")
    print(render(GoldenHour(country="sweden", city="goteborg")))
