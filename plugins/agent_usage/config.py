"""Runtime defaults specific to this plugin.

Presentation constants (the bar width, the colour names, the HTTP timeout)
come from the shared toolkit so every plugin looks and behaves the same.
"""

from __future__ import annotations

import os

from swiftbar.ansi import COLORS as MENU_COLORS
from swiftbar.http import DEFAULT_TIMEOUT as TIMEOUT_SECONDS
from swiftbar.meters import BAR_WIDTH

HOME = os.environ.get("HOME", "")

CACHE_DIR = os.environ.get("SWIFTBAR_PLUGIN_CACHE_PATH") or (
    f"{HOME}/Library/Caches/agent-usage-swiftbar-plugin"
    if HOME
    else "/tmp/agent-usage-swiftbar-plugin"
)

KEYCHAIN_ACCOUNT = next(
    (part for part in reversed(HOME.split("/")) if part), "claude-code"
)

__all__ = [
    "BAR_WIDTH",
    "CACHE_DIR",
    "HOME",
    "KEYCHAIN_ACCOUNT",
    "MENU_COLORS",
    "TIMEOUT_SECONDS",
]
