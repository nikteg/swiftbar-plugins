"""Parsing the assorted timestamp shapes that APIs return."""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

MS_PER_SECOND = 1000
MS_PER_MINUTE = 60_000
MS_PER_HOUR = 3_600_000
MS_PER_DAY = 86_400_000

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

_ISO_PATTERN = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6})\d*)?)?"
    r"(Z|[+-]\d{2}:?\d{2})?)?$"
)


def now_ms() -> float:
    return time.time() * MS_PER_SECOND


def from_ms(value: float) -> datetime:
    return datetime.fromtimestamp(value / MS_PER_SECOND, UTC)


def to_ms(value: datetime | None) -> float | None:
    return None if value is None else value.timestamp() * MS_PER_SECOND


def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


def parse_date(value: Any) -> datetime | None:
    """Accepts epoch seconds, epoch milliseconds, or an ISO-8601 string."""

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        if not _is_finite(float(value)):
            return None
        # Anything past year 2286 in seconds is really milliseconds.
        seconds = value if abs(value) >= 10_000_000_000 else value * 1000

        try:
            return datetime.fromtimestamp(seconds / 1000, UTC)
        except (OverflowError, OSError, ValueError):
            return None

    if not isinstance(value, str) or not value:
        return None

    if re.fullmatch(r"\d+", value):
        return parse_date(int(value))

    match = _ISO_PATTERN.match(value.strip())

    if not match:
        return None

    year, month, day, hour, minute, second, fraction, offset = match.groups()
    parsed = datetime(
        int(year),
        int(month),
        int(day),
        int(hour or 0),
        int(minute or 0),
        int(second or 0),
        int((fraction or "").ljust(6, "0") or 0),
    )

    if offset is None:
        # A date-time without a zone is local; a bare date is UTC midnight.
        if hour is not None:
            return parsed.astimezone()

        return parsed.replace(tzinfo=UTC)

    if offset == "Z":
        return parsed.replace(tzinfo=UTC)

    sign = 1 if offset[0] == "+" else -1
    digits = offset[1:].replace(":", "")
    delta = timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))

    return parsed.replace(tzinfo=timezone(sign * delta))


def relative(target: datetime, *, prefix: str = "in ") -> str:
    """Renders a future instant as ``in 4d 3h`` / ``in 12m``."""
    milliseconds = (target - datetime.now(target.tzinfo)).total_seconds() * 1000

    if milliseconds <= 0:
        return "due"

    minutes = -(-int(milliseconds) // MS_PER_MINUTE)  # ceil
    days, remainder = divmod(minutes, 1440)
    hours, mins = divmod(remainder, 60)

    if days > 0:
        return f"{prefix}{days}d {hours}h"

    if hours > 0:
        return f"{prefix}{hours}h {mins}m"

    return f"{prefix}{mins}m"
