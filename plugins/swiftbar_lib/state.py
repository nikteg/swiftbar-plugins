"""Small JSON state files, one directory per plugin."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

#: SwiftBar sets this when it gives the plugin a cache directory of its own.
CACHE_ENV = "SWIFTBAR_PLUGIN_CACHE_PATH"


def state_dir(plugin: str) -> Path:
    base = os.environ.get(CACHE_ENV)
    root = Path(base) if base else Path.home() / "Library/Caches/swiftbar-plugins"

    return root / plugin


def state_path(plugin: str, name: str = "state.json") -> Path:
    return state_dir(plugin) / name


def load(plugin: str, name: str = "state.json", default: Any = None) -> Any:
    """Reads state, treating any failure as "nothing stored yet"."""

    try:
        with open(state_path(plugin, name), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {} if default is None else default


def save(
    plugin: str, value: Any, name: str = "state.json", *, private: bool = False
) -> None:
    """Replaces the file atomically, so a crashed run cannot truncate it."""
    write_json(state_path(plugin, name), value, private=private)


def write_json(path: Path | str, value: Any, *, private: bool = False) -> None:
    """Atomic JSON write. ``private`` makes the file owner-only, for secrets."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.{os.getpid()}.tmp")
    payload = json.dumps(value, indent=2) + "\n"

    try:
        if private:
            # Opened owner-only rather than chmod'd afterwards, so the contents
            # are never briefly world-readable.
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC

            with open(
                os.open(temporary, flags, 0o600), "w", encoding="utf-8"
            ) as handle:
                handle.write(payload)
        else:
            temporary.write_text(payload, encoding="utf-8")

        os.replace(temporary, path)

        if private:
            os.chmod(path, 0o600)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
