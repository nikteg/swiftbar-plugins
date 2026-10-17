"""Usage recorded by OpenCode in its SQLite store, shared by several providers."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from ..config import HOME
from ..utils import MS_PER_DAY, now_ms, number_at, object_at, string_at

RETENTION_MS = 32 * MS_PER_DAY
DATA_DIR = os.path.join(HOME, ".local", "share", "opencode")
DATABASE_PATH = os.path.join(DATA_DIR, "opencode.db")

# OpenCode 2 keeps legacy `message` rows next to the newer `session_message`
# rows; both carry per-call tokens and cost in a JSON `data` column.
QUERIES = (
    "SELECT time_created, data FROM message WHERE time_created >= ?",
    "SELECT time_created, data FROM session_message"
    " WHERE type = 'assistant' AND time_created >= ?",
)


@dataclass
class OpenCodeUsageEvent:
    timestamp: float
    provider: str
    input_tokens: float
    output_tokens: float
    reasoning_tokens: float
    cache_read_tokens: float
    cache_write_tokens: float
    total_tokens: float
    cost: float
    model: str | None = None


def parse_opencode_usage_event(
    value: Any, timestamp: float | None = None
) -> OpenCodeUsageEvent | None:
    """Parses a legacy `message` or OpenCode 2 `session_message` payload."""
    if not isinstance(value, dict) or value.get("role", "assistant") != "assistant":
        return None
    model = object_at(value, "model")
    provider = string_at(value, "providerID") or string_at(model, "providerID")
    tokens = object_at(value, "tokens")
    created = number_at(object_at(value, "time"), "created") or timestamp
    if not provider or tokens is None or created is None:
        return None
    cache = object_at(tokens, "cache")
    event = OpenCodeUsageEvent(
        timestamp=created,
        provider=provider,
        model=string_at(value, "modelID") or string_at(model, "id"),
        input_tokens=number_at(tokens, "input") or 0.0,
        output_tokens=number_at(tokens, "output") or 0.0,
        reasoning_tokens=number_at(tokens, "reasoning") or 0.0,
        cache_read_tokens=number_at(cache, "read") or 0.0,
        cache_write_tokens=number_at(cache, "write") or 0.0,
        total_tokens=0.0,
        cost=number_at(value, "cost") or 0.0,
    )
    event.total_tokens = number_at(tokens, "total") or (
        event.input_tokens
        + event.output_tokens
        + event.reasoning_tokens
        + event.cache_read_tokens
        + event.cache_write_tokens
    )
    return event if event.total_tokens > 0 else None


_cached_events: list[OpenCodeUsageEvent] | None = None
_scan_lock = threading.Lock()


def collect_opencode_usage_events() -> list[OpenCodeUsageEvent]:
    """Reads OpenCode once per refresh and shares neutral events with providers."""
    global _cached_events
    with _scan_lock:
        if _cached_events is None:
            _cached_events = _scan(DATABASE_PATH)
        return _cached_events


def _scan(path: str) -> list[OpenCodeUsageEvent]:
    if not os.path.exists(path):
        return []
    cutoff = now_ms() - RETENTION_MS
    events = []
    connection = sqlite3.connect(f"file:{quote(path)}?mode=ro", uri=True, timeout=2)
    try:
        for query in QUERIES:
            try:
                rows = connection.execute(query, (cutoff,)).fetchall()
            except sqlite3.OperationalError:
                continue  # Table absent in this OpenCode version.
            for time_created, data in rows:
                try:
                    value = json.loads(data)
                except (TypeError, ValueError):
                    continue
                event = parse_opencode_usage_event(value, time_created)
                if event:
                    events.append(event)
    finally:
        connection.close()
    return events
