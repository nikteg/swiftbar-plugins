"""Usage read from Claude Code session transcripts."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from ..config import CACHE_DIR, HOME
from ..session_cache import JsonlCache
from ..utils import (
    MS_PER_DAY,
    now_ms,
    number_at,
    object_at,
    parse_date,
    read_json,
    string_at,
    to_ms,
)

RETENTION_MS = 8 * MS_PER_DAY

_SESSION_ID_PATTERN = re.compile(
    r"/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"(?:\.jsonl|/subagents/)"
)
_DESKTOP_SESSION_FILE = re.compile(r"^local_.+\.json$")


@dataclass
class ClaudeUsageEvent:
    event_id: str
    timestamp: float
    total_tokens: float
    uncached_tokens: float


def parse_claude_usage_event(value: Any) -> ClaudeUsageEvent | None:
    if not isinstance(value, dict) or value.get("type") != "assistant":
        return None

    message = object_at(value, "message") or {}
    usage = object_at(message, "usage")
    timestamp = to_ms(parse_date(value.get("timestamp")))
    event_id = (
        string_at(value, "requestId")
        or string_at(message, "id")
        or string_at(value, "uuid")
    )
    stop_reason = string_at(message, "stop_reason")
    model = string_at(message, "model")
    input_tokens = number_at(usage, "input_tokens")
    output_tokens = number_at(usage, "output_tokens")

    if (
        timestamp is None
        or event_id is None
        or stop_reason is None
        or model == "<synthetic>"
        or input_tokens is None
        or output_tokens is None
    ):
        return None

    cache_read = number_at(usage, "cache_read_input_tokens") or 0.0
    cache_write = number_at(usage, "cache_creation_input_tokens") or 0.0

    return ClaudeUsageEvent(
        event_id=event_id,
        timestamp=timestamp,
        total_tokens=input_tokens + cache_read + cache_write + output_tokens,
        uncached_tokens=input_tokens + cache_write + output_tokens,
    )


def _decode(value: Any) -> ClaudeUsageEvent | None:
    if not isinstance(value, dict):
        return None

    try:
        event = ClaudeUsageEvent(**value)
    except TypeError:
        return None

    if not isinstance(event.event_id, str):
        return None

    numbers = (event.timestamp, event.total_tokens, event.uncached_tokens)

    return event if all(isinstance(n, (int, float)) for n in numbers) else None


def collect_claude_usage_events(
    config_dir: str,
    cache_suffix: str,
    now: float | None = None,
    additional_session_ids: Iterable[str] | None = None,
    excluded_session_ids: Iterable[str] | None = None,
) -> list[ClaudeUsageEvent]:
    now = now_ms() if now is None else now
    additional = set(additional_session_ids or ())
    excluded = set(excluded_session_ids or ())
    files = _session_files(config_dir, now, excluded_session_ids=excluded)

    if additional:
        files.extend(
            _session_files(
                os.path.join(HOME, ".claude"), now, included_session_ids=additional
            )
        )

    cache = JsonlCache(
        cache_path=os.path.join(CACHE_DIR, f"claude-sessions-{cache_suffix}.json"),
        version="claude-events-py1",
        now=now,
        retention_ms=RETENTION_MS,
        parse=lambda record, state: (state, parse_claude_usage_event(record)),
        encode_event=asdict,
        decode_event=_decode,
        event_timestamp=lambda event: event.timestamp,
    )
    unique = dict.fromkeys(files)
    by_id = {event.event_id: event for event in cache.events(list(unique))}

    return list(by_id.values())


def claude_desktop_session_ids(data_dir: str) -> set[str]:
    """Session ids Claude Desktop launched, used to attribute them to a profile."""
    session_ids = set()
    root = os.path.join(data_dir, "claude-code-sessions")

    for directory, _directories, names in os.walk(root):
        for name in names:
            if _DESKTOP_SESSION_FILE.match(name):
                session_id = string_at(
                    read_json(os.path.join(directory, name)), "cliSessionId"
                )

                if session_id:
                    session_ids.add(session_id)

    return session_ids


def _session_files(
    config_dir: str,
    now: float,
    included_session_ids: set[str] | None = None,
    excluded_session_ids: set[str] | None = None,
) -> list[str]:
    cutoff = now - RETENTION_MS
    files = []

    for directory, _directories, names in os.walk(os.path.join(config_dir, "projects")):
        for name in names:
            if not name.endswith(".jsonl"):
                continue

            path = os.path.join(directory, name)
            session_id = _session_id_from_path(path) or ""

            if (
                included_session_ids is not None
                and session_id not in included_session_ids
            ):
                continue

            if excluded_session_ids and session_id in excluded_session_ids:
                continue

            try:
                modified = os.path.getmtime(path) * 1000
            except OSError:
                continue

            if modified >= cutoff:
                files.append(path)

    return files


def _session_id_from_path(path: str) -> str | None:
    match = _SESSION_ID_PATTERN.search(path)

    return match.group(1) if match else None
