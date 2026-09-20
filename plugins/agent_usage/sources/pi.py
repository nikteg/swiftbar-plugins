"""Usage recorded by the Pi session harness, shared by several providers."""

from __future__ import annotations

import os
import threading
from dataclasses import asdict, dataclass
from typing import Any

from swiftbar_lib.jsonl_cache import JsonlCache

from ..config import CACHE_DIR, HOME
from ..utils import (
    MS_PER_DAY,
    now_ms,
    number_at,
    object_at,
    parse_date,
    string_at,
    to_ms,
)

RETENTION_MS = 32 * MS_PER_DAY


@dataclass
class PiUsageEvent:
    timestamp: float
    provider: str
    input_tokens: float
    output_tokens: float
    cache_read_tokens: float
    cache_write_tokens: float
    total_tokens: float
    cost: float
    model: str | None = None


def parse_pi_usage_event(value: Any) -> PiUsageEvent | None:
    if not isinstance(value, dict) or value.get("type") != "message":
        return None

    message = object_at(value, "message")

    if message is None or message.get("role") != "assistant":
        return None

    provider = string_at(message, "provider")
    usage = object_at(message, "usage")
    timestamp = to_ms(parse_date(value.get("timestamp")))
    total_tokens = number_at(usage, "totalTokens")

    if not provider or timestamp is None or total_tokens is None:
        return None

    return PiUsageEvent(
        timestamp=timestamp,
        provider=provider,
        model=string_at(message, "model"),
        input_tokens=number_at(usage, "input") or 0.0,
        output_tokens=number_at(usage, "output") or 0.0,
        cache_read_tokens=number_at(usage, "cacheRead") or 0.0,
        cache_write_tokens=number_at(usage, "cacheWrite") or 0.0,
        total_tokens=total_tokens,
        cost=number_at(object_at(usage, "cost"), "total") or 0.0,
    )


def _decode(value: Any) -> PiUsageEvent | None:
    if not isinstance(value, dict):
        return None

    try:
        event = PiUsageEvent(**value)
    except TypeError:
        return None

    numbers = (
        event.timestamp,
        event.input_tokens,
        event.output_tokens,
        event.cache_read_tokens,
        event.cache_write_tokens,
        event.total_tokens,
        event.cost,
    )

    if not all(isinstance(number, (int, float)) for number in numbers):
        return None

    if not isinstance(event.provider, str):
        return None

    return event if event.model is None or isinstance(event.model, str) else None


def _session_files() -> list[str]:
    root = os.path.join(HOME, ".pi", "agent", "sessions")
    cutoff = now_ms() - RETENTION_MS
    files = []

    try:
        projects = os.listdir(root)
    except FileNotFoundError:
        return files

    for project in projects:
        directory = os.path.join(root, project)

        try:
            names = os.listdir(directory)
        except (FileNotFoundError, NotADirectoryError):
            continue

        for name in names:
            path = os.path.join(directory, name)

            if name.endswith(".jsonl") and os.path.getmtime(path) * 1000 >= cutoff:
                files.append(path)

    return files


_cached_events: list[PiUsageEvent] | None = None
_scan_lock = threading.Lock()


def collect_pi_usage_events() -> list[PiUsageEvent]:
    """Scans Pi once per refresh and shares neutral events with all providers.

    Providers are collected on a thread pool, so the scan is guarded: the first
    caller reads the sessions and the rest reuse the same events.
    """
    global _cached_events

    with _scan_lock:
        if _cached_events is None:
            _cached_events = _scan()

        return _cached_events


def _scan() -> list[PiUsageEvent]:
    cache = JsonlCache(
        cache_path=os.path.join(CACHE_DIR, "pi-sessions.json"),
        version="pi-events-py1",
        now=now_ms(),
        retention_ms=RETENTION_MS,
        parse=lambda record, state: (state, parse_pi_usage_event(record)),
        encode_event=asdict,
        decode_event=_decode,
        event_timestamp=lambda event: event.timestamp,
    )

    return cache.events(_session_files())
