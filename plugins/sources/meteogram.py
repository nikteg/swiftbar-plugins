"""Golden hour scraped from meteogram.org, which publishes no API."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser

from swiftbar_lib.http import get_text

BASE_URL = "https://meteogram.org/sun"
EVENING_CELL_CLASS = "avond_goudenhour"


@dataclass(frozen=True)
class GoldenHour:
    times: str
    location: str
    url: str


class _Scraper(HTMLParser):
    """Pulls one table cell and the description meta tag out of the page.

    stdlib rather than a parser dependency: two values are not worth a wheel,
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


def evening(country: str, city: str) -> GoldenHour:
    """Tonight's golden hour. ``times`` is empty when the page has no cell."""
    url = f"{BASE_URL}/{country}/{city}/"
    scraper = _Scraper(EVENING_CELL_CLASS)
    scraper.feed(get_text(url))

    return GoldenHour(
        times=" ".join(scraper.times.split()),
        location=scraper.description.split("-")[0].strip() or city,
        url=url,
    )
