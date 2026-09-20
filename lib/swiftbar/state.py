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


def save(plugin: str, value: Any, name: str = "state.json") -> None:
    """Replaces the file atomically, so a crashed run cannot truncate it."""
    path = state_path(plugin, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.{os.getpid()}.tmp")

    try:
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def clear(plugin: str) -> int:
    """Deletes this plugin's state files and reports how many were removed."""
    directory = state_dir(plugin)
    removed = 0

    for entry in directory.glob("*.json") if directory.is_dir() else []:
        entry.unlink(missing_ok=True)
        removed += 1

    return removed
