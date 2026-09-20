"""Helpers specific to agent usage: JSON shapes, credentials, quota meters.

Generic helpers (dates, number formatting, menu escaping, error cleanup) are
re-exported from the shared toolkit so provider modules have a single import
site and the two copies cannot drift apart.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from swiftbar.dates import (
    MS_PER_DAY,
    MS_PER_HOUR,
    MS_PER_MINUTE,
    MS_PER_SECOND,
    from_ms,
    now_ms,
    parse_date,
    to_ms,
)
from swiftbar.meters import clamp_percent, compact_number, round_half_up
from swiftbar.output import escape as swiftbar_escape
from swiftbar.plugin import clean_error

from .config import TIMEOUT_SECONDS
from .types import Meter


def object_at(value: Any, key: str) -> dict | None:
    child = value.get(key) if isinstance(value, dict) else None

    return child if isinstance(child, dict) else None


def string_at(value: Any, key: str) -> str | None:
    child = value.get(key) if isinstance(value, dict) else None

    return child if isinstance(child, str) and child else None


def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


def number_value(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value) if _is_finite(value) else None

    if isinstance(value, str):
        if not value.strip():
            return None

        try:
            parsed = float(value)
        except ValueError:
            return None

        return parsed if _is_finite(parsed) else None

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


def fetch_json(
    url: str, headers: Mapping[str, str], method: str = "GET"
) -> tuple[dict, Mapping[str, str]]:
    request = urllib.request.Request(url, method=method, headers=dict(headers))

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
            response_headers = response.headers
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"HTTP {error.code}") from None
    except urllib.error.URLError as error:
        raise _url_error(error) from None

    if not isinstance(body, dict):
        raise RuntimeError("unexpected response")

    return body, response_headers


def post_json(url: str, body: dict | list) -> dict:
    """Posts JSON, or form-encoded pairs when ``body`` is a list of tuples."""
    is_form = isinstance(body, list)
    payload = (
        urllib.parse.urlencode(body).encode() if is_form else json.dumps(body).encode()
    )
    content_type = (
        "application/x-www-form-urlencoded" if is_form else "application/json"
    )
    request = urllib.request.Request(
        url, data=payload, method="POST", headers={"Content-Type": content_type}
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"token refresh failed (HTTP {error.code})") from None
    except urllib.error.URLError as error:
        raise _url_error(error) from None

    if not isinstance(value, dict):
        raise RuntimeError("unexpected token response")

    return value


def _url_error(error: urllib.error.URLError) -> Exception:
    if isinstance(error.reason, (socket.timeout, TimeoutError)):
        return TimeoutError("Request timed out")

    return RuntimeError(str(error.reason))


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


def write_private_json(path: str, value: dict) -> None:
    """Replaces ``path`` atomically with owner-only permissions."""
    temporary = f"{path}.agent-usage-{os.getpid()}.tmp"

    try:
        with open(
            os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(json.dumps(value, indent=2) + "\n")

        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except OSError:
        _remove_quietly(temporary)
        raise


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass  # Best-effort cleanup; preserve the original failure.


#: Re-exported from the toolkit so provider modules have one import site.
__all__ = [
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
    "write_private_json",
]
