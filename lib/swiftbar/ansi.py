"""ANSI colouring for menu rows.

SwiftBar renders these only when the row carries ``ansi=true``, so the helpers
that emit coloured text set it for you.
"""

from __future__ import annotations

RESET = "\x1b[0m"

#: Semantic names rather than colours, so a plugin states intent.
COLORS = {
    "normal": 32,
    "warning": 33,
    "critical": 31,
    "activity": 34,
    "unknown": 90,
    "accent": 35,
    "muted": 90,
}


def colorize(text: str, level: str) -> str:
    code = COLORS.get(level)

    return text if code is None else f"\x1b[{code}m{text}{RESET}"


def level_for(used_percent: float, warning: float = 75, critical: float = 90) -> str:
    """Maps a percentage to a severity name."""

    if used_percent >= critical:
        return "critical"

    if used_percent >= warning:
        return "warning"

    return "normal"
