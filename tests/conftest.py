"""Keeps the offline suite offline.

Codex credit figures are derived from OpenAI's published prices, which the
plugin fetches at runtime. Without this, importing those tests reached
developers.openai.com and asserted on whatever the price list said that day —
so the suite passed or failed depending on the network and the calendar.
"""

import tempfile
from pathlib import Path

import pytest

from agent_usage.pricing import codex, openai
from swiftbar_lib import config

#: Plugins read personal settings from ~/.config when they are imported, which
#: happens as test modules load, before any fixture runs. Pointing the config
#: directory at an empty one here keeps your own settings out of the suite.
config.CONFIG_DIR = Path(tempfile.mkdtemp(prefix="swiftbar-config-"))

#: A frozen snapshot, in the format the real parser consumes, so these tests
#: exercise the parser too. The figures are OpenAI's published prices as of
#: 2026-09-20; they are a fixture, not a claim about today's pricing.
PRICES_MARKDOWN = """
### Standard pricing data
| Model | in | cached in | writes | out | long in | long cached | long writes | long out |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-5.6-luna | $0.20 | $0.02 | $0.25 | $1.20 | $0.40 | $0.04 | $0.50 | $1.80 |
| gpt-5.6-sol | $1.25 | $0.125 | $1.25 | $10.00 | $2.50 | $0.25 | $2.50 | $15.00 |
| gpt-5.5 | $5.00 | $0.50 | $5.00 | $30.00 | $10.00 | $1.00 | $10.00 | $45.00 |
| gpt-5.5-pro | $15.00 | $1.50 | $15.00 | $120.00 | $30.00 | $3.00 | $30.00 | $180.00 |
| gpt-5.2 | $1.25 | $0.125 | $1.25 | $10.00 | $2.50 | $0.25 | $2.50 | $15.00 |
### Batch pricing data
"""


def _clear_price_caches():
    openai.load.cache_clear()
    codex.codex_prices.cache_clear()
    codex.credit_rates.cache_clear()
    codex._ranked_rates.cache_clear()
    codex.pricing_cache_version.cache_clear()


@pytest.fixture(autouse=True)
def frozen_prices(tmp_path, monkeypatch):
    """Every test sees the snapshot above, and none of them touch the network."""
    monkeypatch.setattr(openai, "CACHE_PATH", str(tmp_path / "openai-prices.json"))
    monkeypatch.setattr(
        openai, "fetch", lambda: openai.parse_standard_prices(PRICES_MARKDOWN)
    )
    _clear_price_caches()

    yield

    _clear_price_caches()
