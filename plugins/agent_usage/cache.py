"""Which cache files belong to this plugin, and clearing just those."""

from __future__ import annotations

import os

from .config import CACHE_DIR

SESSION_CACHE_FILENAMES = ("codex-sessions.json", "pi-sessions.json")
SESSION_CACHE_PREFIXES = ("claude-sessions-",)
PRICE_CACHE_FILENAME = "openai-prices.json"


def clear_session_caches(directory: str = CACHE_DIR) -> int:
    """Removes only cache files this plugin owns, never logs or credentials."""
    removed = 0

    for filename in (*SESSION_CACHE_FILENAMES, PRICE_CACHE_FILENAME):
        removed += _remove(os.path.join(directory, filename))

    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        return removed

    for name in names:
        if name.endswith(".json") and name.startswith(SESSION_CACHE_PREFIXES):
            path = os.path.join(directory, name)

            if os.path.isfile(path):
                removed += _remove(path)

    return removed


def _remove(path: str) -> int:
    try:
        os.remove(path)

        return 1
    except FileNotFoundError:
        return 0
