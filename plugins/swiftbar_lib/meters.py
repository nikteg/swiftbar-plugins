"""Number formatting and the filled-circle progress bar."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

BAR_WIDTH = 12
FILLED = "●"
EMPTY = "○"


def clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, value))


def round_half_up(value: float, digits: int = 0) -> float:
    """Rounds like a person expects, unlike Python's banker's rounding."""
    quantum = Decimal(1).scaleb(-digits)

    return float(Decimal(repr(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def bar(used_percent: float, width: int = BAR_WIDTH) -> str:
    filled = int(round_half_up(clamp_percent(used_percent) / 100 * width))

    return FILLED * filled + EMPTY * (width - filled)


def compact_number(value: float) -> str:
    """Formats like Intl compact notation: 1.2K, 3.4M, 12."""

    for limit, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        # Rounded first: at 999.95 the unrounded value is under 1e3 but the
        # rendered one is not, which used to print "1000" instead of "1K".
        if abs(round_half_up(value, 1)) >= limit:
            return _trim(round_half_up(value / limit, 1)) + suffix

    return _trim(round_half_up(value, 1))


def _trim(value: float) -> str:
    text = f"{value:.1f}"

    return text[:-2] if text.endswith(".0") else text
