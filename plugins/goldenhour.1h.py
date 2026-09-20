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

from html.parser import HTMLParser

from swiftbar.http import get_text
from swiftbar.output import Menu
from swiftbar.plugin import run as run_plugin

BASE_URL = "https://meteogram.org/sun"


class Scraper(HTMLParser):
    """Pulls one table cell and the description meta tag out of the page.

    stdlib rather than a parser dependency: two values is not worth a wheel,
    and a plugin that installs nothing cannot break on a stale one.
    """

    def __init__(self, cell_class: str) -> None:
        super().__init__(convert_charrefs=True)
        self._cell_class = cell_class
        self._depth = 0
        self.times: str = ""
        self.description: str = ""

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)

        if tag == "meta" and values.get("name") == "description":
            self.description = values.get("content") or ""

        if tag == "td" and self._cell_class in (values.get("class") or "").split():
            self._depth = 1
        elif self._depth:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._depth:
            self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._depth:
            self.times += data


def run(country: str = "sweden", city: str = "goteborg") -> int:
    url = f"{BASE_URL}/{country}/{city}/"

    def build(menu: Menu) -> None:
        scraper = Scraper("avond_goudenhour")
        scraper.feed(get_text(url))
        times = " ".join(scraper.times.split())

        if not times:
            menu.unavailable("🌇 —", f"No golden hour found for {city}", href=url)

            return

        menu.title(f"🌇 {times} 🌇")
        menu.sep()
        menu.item(scraper.description.split("-")[0].strip() or city, href=url)

    return run_plugin(build, name="Golden hour", icon="🌇")


if __name__ == "__main__":
    raise SystemExit(run(country="sweden", city="goteborg"))
