"""Incremental reading of append-only JSONL files across plugin runs.

A SwiftBar plugin is a fresh process every refresh, so anything that scans
a growing log re-reads it from the start unless it remembers where it got
to. This keeps a byte offset and the events parsed so far for each file,
reads only what has been appended, and rescans from scratch when a file is
truncated, rewritten in place, or the parser version changes.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _CachedFile:
    size: int = 0
    mtime_ms: float = 0.0
    offset: int = 0
    state: dict = field(default_factory=dict)
    events: list = field(default_factory=list)


@dataclass
class JsonlCache[E]:
    """Reuses parsed JSONL events across SwiftBar runs, reading only new bytes.

    A parser-version change, truncation, or in-place rewrite forces a safe full
    rescan of the affected file.
    """

    cache_path: str
    version: str
    now: float
    retention_ms: float
    #: ``(record, state) -> (next_state, event | None)``
    parse: Callable[[Any, dict], tuple[dict, E | None]]
    encode_event: Callable[[E], dict]
    decode_event: Callable[[dict], E | None]
    event_timestamp: Callable[[E], float]
    initial_state: Callable[[], dict] = dict

    def events(self, files: Sequence[str]) -> list[E]:
        previous = self._read_cache()
        current: dict[str, _CachedFile] = {}
        collected: list[E] = []
        cutoff = self.now - self.retention_ms

        for path in files:
            try:
                stat = os.stat(path)
            except FileNotFoundError:
                continue

            mtime_ms = stat.st_mtime * 1000
            cached = previous.get(path) or _CachedFile(state=self.initial_state())

            if self._rewritten(stat.st_size, mtime_ms, cached):
                cached = _CachedFile(state=self.initial_state())

            cached.events = [
                event
                for event in cached.events
                if self.event_timestamp(event) >= cutoff
            ]

            if stat.st_size > cached.offset:
                self._ingest(path, cached, cutoff)

            cached.size = stat.st_size
            cached.mtime_ms = mtime_ms
            current[path] = cached
            collected.extend(cached.events)

        self._write_cache(current)

        return collected

    @staticmethod
    def _rewritten(size: int, mtime_ms: float, cached: _CachedFile) -> bool:
        return (
            size < cached.size
            or size < cached.offset
            or (size == cached.size and mtime_ms != cached.mtime_ms)
        )

    def _ingest(self, path: str, cached: _CachedFile, cutoff: float) -> None:
        with open(path, "rb") as handle:
            handle.seek(cached.offset)
            appended = handle.read()

        newline = appended.rfind(b"\n")

        if newline < 0:
            return  # Only a partial record has been written so far.

        complete = appended[: newline + 1]
        cached.offset += len(complete)

        for line in complete.decode("utf-8", "replace").splitlines():
            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except ValueError:
                continue  # Corrupt records are skipped, as in an uncached read.

            cached.state, event = self.parse(record, cached.state)

            if event is not None and self.event_timestamp(event) >= cutoff:
                cached.events.append(event)

    def _read_cache(self) -> dict[str, _CachedFile]:
        try:
            with open(self.cache_path, encoding="utf-8") as handle:
                document = json.load(handle)
        except (OSError, ValueError):
            return {}  # Missing or corrupt caches are ordinary misses.

        if not isinstance(document, dict) or document.get("version") != self.version:
            return {}

        raw_files = document.get("files")

        if not isinstance(raw_files, dict):
            return {}

        files: dict[str, _CachedFile] = {}

        for path, raw in raw_files.items():
            entry = self._decode_file(raw)

            if entry is not None:
                files[path] = entry

        return files

    def _decode_file(self, raw: Any) -> _CachedFile | None:
        if not isinstance(raw, dict) or not isinstance(raw.get("state"), dict):
            return None

        numbers = [_non_negative(raw.get(key)) for key in ("size", "mtimeMs", "offset")]

        if any(number is None for number in numbers) or not isinstance(
            raw.get("events"), list
        ):
            return None

        events = [self.decode_event(value) for value in raw["events"]]

        return _CachedFile(
            size=int(numbers[0]),
            mtime_ms=numbers[1],
            offset=int(numbers[2]),
            state=raw["state"],
            events=[event for event in events if event is not None],
        )

    def _write_cache(self, files: dict[str, _CachedFile]) -> None:
        document = {
            "version": self.version,
            "files": {
                path: {
                    "size": cached.size,
                    "mtimeMs": cached.mtime_ms,
                    "offset": cached.offset,
                    "state": cached.state,
                    "events": [self.encode_event(event) for event in cached.events],
                }
                for path, cached in files.items()
            },
        }
        temporary = f"{self.cache_path}.{os.getpid()}.tmp"

        try:
            os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)

            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(document, handle)
                handle.write("\n")

            os.replace(temporary, self.cache_path)
        except OSError:
            # Caching is an optimization; collection must succeed without it.
            try:
                os.remove(temporary)
            except OSError:
                pass


def _non_negative(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    return float(value) if value >= 0 else None
