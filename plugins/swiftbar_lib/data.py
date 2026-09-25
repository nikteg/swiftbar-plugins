"""Reading values out of untyped JSON without trusting its shape.

An API response is not a schema. Indexing it directly is how a plugin turns a
renamed field into a stack trace in the menu bar, so these return ``None``
instead of raising and never guess at a type.
"""

from __future__ import annotations

import json
from typing import Any


def object_at(value: Any, key: str) -> dict | None:
    child = value.get(key) if isinstance(value, dict) else None

    return child if isinstance(child, dict) else None


def string_at(value: Any, key: str) -> str | None:
    """The value at ``key`` when it is a non-empty string."""
    child = value.get(key) if isinstance(value, dict) else None

    return child if isinstance(child, str) and child else None


def strings_at(value: Any, key: str) -> list[str]:
    """The non-empty strings in the list at ``key``; anything else is dropped."""
    child = value.get(key) if isinstance(value, dict) else None

    if not isinstance(child, list):
        return []

    return [item for item in child if isinstance(item, str) and item]


def is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


def number_value(value: Any) -> float | None:
    """A float from a number or a numeric string, rejecting bools and NaN."""
    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value) if is_finite(value) else None

    if isinstance(value, str):
        if not value.strip():
            return None

        try:
            parsed = float(value)
        except ValueError:
            return None

        return parsed if is_finite(parsed) else None

    return None


def number_at(value: Any, key: str) -> float | None:
    return number_value(value.get(key)) if isinstance(value, dict) else None


def read_json(path: str) -> dict | None:
    """Reads a JSON object, treating any failure as "not configured"."""
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError):
        return None

    return value if isinstance(value, dict) else None
