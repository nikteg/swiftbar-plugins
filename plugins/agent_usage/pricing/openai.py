"""OpenAI's published token prices, fetched on demand and cached for a month.

Prices used to be a generated file refreshed by a make target, which meant a
checkout could sit on stale numbers indefinitely and the repo carried machine
-written data. The plugin now fetches them itself and caches the result, so the
only manual step left is deleting the cache.

Every failure degrades rather than raises: a stale cache is preferred to no
prices, and no prices at all costs only the local spend estimate, never the
quota figures that come from the provider APIs.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from functools import cache

from ..config import CACHE_DIR
from .types import ModelPrice

PRICING_URL = "https://developers.openai.com/api/docs/pricing.md"
CACHE_PATH = os.path.join(CACHE_DIR, "openai-prices.json")

#: Published prices move a few times a year, so a month is frequent enough to
#: stay accurate and rare enough that almost no refresh pays for the fetch.
MAX_AGE_SECONDS = 30 * 24 * 3600
FETCH_TIMEOUT_SECONDS = 20

LONG_CONTEXT_THRESHOLD_TOKENS = 272_000


def parse_money(value: str) -> float | None:
    if value == "-":
        return None

    match = re.fullmatch(r"\$([\d,]+(?:\.\d+)?)", value)

    if not match:
        raise ValueError(f"unexpected price value: {value}")

    return float(match.group(1).replace(",", ""))


def parse_standard_prices(markdown: str) -> dict[str, ModelPrice]:
    """Reads the standard-pricing table out of OpenAI's published markdown."""
    start = markdown.find("### Standard pricing data")
    end = markdown.find("### Batch pricing data", start)

    if start < 0 or end < 0:
        raise ValueError("could not locate OpenAI standard pricing table")

    prices: dict[str, ModelPrice] = {}

    for line in markdown[start:end].split("\n"):
        if not line.startswith("|"):
            continue

        cells = [cell.strip() for cell in line.split("|")[1:-1]]

        if len(cells) < 5 or cells[0] == "Model" or cells[0].startswith("---"):
            continue

        model = re.sub(r"\s+\([^)]*\)$", "", cells[0])
        input_price = parse_money(cells[1])
        cached_input = parse_money(cells[2])
        cache_write = parse_money(cells[3])
        output = parse_money(cells[4])

        if input_price is None or output is None:
            raise ValueError(f"missing input/output price for {model}")

        if model in prices:
            raise ValueError(f"duplicate model: {model}")

        long_input, long_cached, long_write, long_output = (
            parse_money(cells[index] if index < len(cells) else "-")
            for index in range(5, 9)
        )
        price = {
            "input": input_price,
            # A dash means there is no cached-input discount, so cached tokens
            # use the normal input price for the local estimate.
            "cached_input": input_price if cached_input is None else cached_input,
            "cache_write": input_price if cache_write is None else cache_write,
            "output": output,
        }

        if long_input is not None and long_output is not None:
            price["long_context"] = {
                "threshold_tokens": LONG_CONTEXT_THRESHOLD_TOKENS,
                "input": long_input,
                "cached_input": long_input if long_cached is None else long_cached,
                "cache_write": long_input if long_write is None else long_write,
                "output": long_output,
            }

        prices[model] = ModelPrice.from_dict(price)

    if not prices:
        raise ValueError("OpenAI pricing table was empty")

    return dict(sorted(prices.items()))


def fetch() -> dict[str, ModelPrice]:
    request = urllib.request.Request(
        PRICING_URL, headers={"User-Agent": "swiftbar-plugins (python urllib)"}
    )

    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        return parse_standard_prices(response.read().decode("utf-8"))


def read_cache() -> dict[str, ModelPrice] | None:
    try:
        with open(CACHE_PATH, encoding="utf-8") as handle:
            stored = json.load(handle)

        return {
            model: ModelPrice.from_dict(price)
            for model, price in stored["prices"].items()
        }
    except (OSError, ValueError, KeyError, TypeError):
        return None


def cache_age_seconds() -> float:
    try:
        return time.time() - os.path.getmtime(CACHE_PATH)
    except OSError:
        return float("inf")


def write_cache(prices: dict[str, ModelPrice]) -> None:
    payload = {
        "fetched_at": time.time(),
        "prices": {model: price.to_dict() for model, price in prices.items()},
    }
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    temporary = f"{CACHE_PATH}.{os.getpid()}.tmp"

    try:
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")

        os.replace(temporary, CACHE_PATH)
    except OSError:
        try:
            os.remove(temporary)
        except OSError:
            pass  # Preserve the original write error.

        raise


@cache
def load() -> dict[str, ModelPrice]:
    """Cached prices when fresh, otherwise a refetch, otherwise whatever we have."""
    cached = read_cache()

    if cached is not None and cache_age_seconds() < MAX_AGE_SECONDS:
        return cached

    try:
        fetched = fetch()
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        # A stale price list beats none; an empty one only drops cost estimates.
        return cached if cached is not None else {}

    try:
        write_cache(fetched)
    except OSError:
        pass  # Serving the fetch matters more than persisting it.

    return fetched
