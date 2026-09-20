"""Helpers specific to agent usage: quota meters and reset windows.

JSON navigation, atomic writes, HTTP and the generic formatting helpers come
from the shared toolkit and are re-exported here so provider modules keep a
single import site.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from swiftbar_lib.data import (
    is_finite,
    number_at,
    number_value,
    object_at,
    read_json,
    string_at,
)
from swiftbar_lib.dates import (
    MS_PER_DAY,
    MS_PER_HOUR,
    MS_PER_MINUTE,
    MS_PER_SECOND,
    from_ms,
    now_ms,
    parse_date,
    to_ms,
)
from swiftbar_lib.http import get_json_with_headers as fetch_json
from swiftbar_lib.http import post_json
from swiftbar_lib.meters import clamp_percent, compact_number, round_half_up

# Provider-controlled text, so ESC is stripped too: a raw escape code
# could otherwise forge colours or hide content in the menu.
from swiftbar_lib.output import escape_strict as swiftbar_escape
from swiftbar_lib.plugin import clean_error

from .types import Meter


def reset_from_window(window: dict | None) -> datetime | None:
    if not window:
        return None

    absolute = number_at(window, "reset_at")

    if absolute is not None:
        return parse_date(absolute)

    relative = number_at(window, "reset_after_seconds")

    return None if relative is None else from_ms(now_ms() + relative * 1000)


def usage_meter(label: str, source: Any) -> Meter | None:
    if not isinstance(source, dict):
        return None

    utilization = number_at(source, "utilization")

    if utilization is None:
        utilization = number_at(source, "percent")

    if utilization is None:
        return None

    reset = source.get("resets_at", source.get("reset_at", source.get("resetTime")))

    return Meter(
        label=label,
        used_percent=clamp_percent(utilization),
        resets_at=parse_date(reset),
    )


__all__ = [
    "is_finite",
    "MS_PER_DAY",
    "MS_PER_HOUR",
    "MS_PER_MINUTE",
    "MS_PER_SECOND",
    "clamp_percent",
    "clean_error",
    "compact_number",
    "fetch_json",
    "from_ms",
    "now_ms",
    "number_at",
    "number_value",
    "object_at",
    "parse_date",
    "post_json",
    "read_json",
    "reset_from_window",
    "round_half_up",
    "string_at",
    "swiftbar_escape",
    "to_ms",
    "usage_meter",
]
