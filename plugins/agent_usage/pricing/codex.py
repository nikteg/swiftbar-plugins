"""Codex credit estimates derived from published OpenAI token prices.

Everything here is lazy and memoised: prices may involve a network fetch, and
importing a module should never do that.
"""

from __future__ import annotations

import json
from functools import cache

from . import openai
from .types import ModelPrice

# Codex's local activity estimate is expressed in credits, where 25 credits is
# roughly one USD of API-equivalent model usage.
CODEX_CREDITS_PER_USD = 25

CODEX_FALLBACK_MODEL = "gpt-5.5"

# Internal Codex names are linked to public models rather than carrying copied
# prices, so a price refresh updates their estimates too.
CODEX_MODEL_PRICE_ALIASES = {
    "gpt-5.6": "gpt-5.6-sol",
    "gpt-5.2-codex": "gpt-5.2",
    "gpt-5.3-codex": "gpt-5.2",
    "gpt-5.5-cyber": "gpt-5.5-pro",
}


@cache
def codex_prices() -> dict[str, ModelPrice]:
    """Public prices plus the Codex-only aliases that borrow them."""
    prices = dict(openai.load())

    for alias, model in CODEX_MODEL_PRICE_ALIASES.items():
        price = prices.get(model)
        # A missing target means the price list is stale or empty; the alias is
        # simply unpriced rather than fatal.
        if price is not None:
            prices[alias] = price

    return prices


@cache
def credit_rates() -> dict[str, ModelPrice]:
    return {
        model: price.scaled(CODEX_CREDITS_PER_USD)
        for model, price in codex_prices().items()
    }


@cache
def _ranked_rates() -> list[tuple[str, ModelPrice]]:
    # Longest name first, so `gpt-5.2-codex-mini` prefers its own rate.
    return sorted(credit_rates().items(), key=lambda item: -len(item[0]))


@cache
def pricing_cache_version() -> str:
    """Fingerprints the price table so cached estimates expire when it changes."""
    prices = codex_prices()
    serialized = json.dumps(
        [[model, prices[model].to_dict()] for model in sorted(prices)],
        sort_keys=True,
    )

    digest = 2_166_136_261

    for character in serialized:
        digest = ((digest ^ ord(character)) * 16_777_619) & 0xFFFFFFFF

    return format(digest, "08x")


def _rate_for(model: str) -> ModelPrice | None:
    rates = credit_rates()

    if not rates:
        return None

    normalized = model.lower()
    direct = rates.get(normalized)

    if direct is not None:
        return direct

    prefixed = next(
        (value for name, value in _ranked_rates() if normalized.startswith(name + "-")),
        None,
    )

    return prefixed if prefixed is not None else rates.get(CODEX_FALLBACK_MODEL)


def codex_credits(
    model: str,
    input_tokens: float,
    cached_input_tokens: float,
    output_tokens: float,
    cache_write_tokens: float = 0.0,
    context_input_tokens: float | None = None,
) -> float:
    """Credits for one request, or 0 when no price list is available."""
    rate = _rate_for(model)

    if rate is None:
        return 0.0

    if context_input_tokens is None:
        context_input_tokens = input_tokens + cached_input_tokens + cache_write_tokens

    long_context = rate.long_context

    if (
        long_context is not None
        and context_input_tokens > long_context.threshold_tokens
    ):
        rate = long_context

    return (
        max(0.0, input_tokens) * rate.input
        + max(0.0, cached_input_tokens) * rate.cached_input
        + max(0.0, cache_write_tokens) * rate.cache_write
        + max(0.0, output_tokens) * rate.output
    ) / 1_000_000
