"""ANSI colouring for menu rows.

SwiftBar renders these only when the row carries ``ansi=true``, so the helpers
that emit coloured text set it for you.
"""

from __future__ import annotations

import re
from typing import Any

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


_HEX = re.compile(r"^#([0-9a-fA-F]{6})$")

#: The channel values of xterm's 6x6x6 colour cube, indexes 16-231.
_CUBE = (0, 95, 135, 175, 215, 255)


def nearest_256(red: int, green: int, blue: int) -> int:
    """The xterm-256 index closest to an RGB colour, from the cube or the greys."""

    def step(value: int) -> int:
        return min(range(6), key=lambda i: abs(_CUBE[i] - value))

    cube = (step(red), step(green), step(blue))
    grey = min(range(24), key=lambda i: abs(8 + 10 * i - (red + green + blue) / 3))
    candidates = {
        16 + 36 * cube[0] + 6 * cube[1] + cube[2]: tuple(_CUBE[i] for i in cube),
        232 + grey: (8 + 10 * grey,) * 3,
    }

    return min(
        candidates,
        key=lambda index: sum(
            (a - b) ** 2
            for a, b in zip(candidates[index], (red, green, blue), strict=True)
        ),
    )


def sgr(color: Any) -> str | None:
    """The escape parameters for a colour, or None when it is not one.

    A colour is a name from ``COLORS``, an xterm-256 index, or ``"#rrggbb"``.
    SwiftBar understands 256-colour codes but not 24-bit ones, so hex is
    matched to the nearest of the 256.
    """
    if isinstance(color, bool):
        return None

    if isinstance(color, int):
        return f"38;5;{color}" if 0 <= color <= 255 else None

    if not isinstance(color, str):
        return None

    if color in COLORS:
        return str(COLORS[color])

    match = _HEX.match(color)

    if match is None:
        return None

    red, green, blue = (int(match.group(1)[i : i + 2], 16) for i in (0, 2, 4))

    return f"38;5;{nearest_256(red, green, blue)}"


def colorize(text: str, color: Any) -> str:
    """Colours text with anything ``sgr`` accepts; unknown colours leave it plain."""
    code = sgr(color)

    return text if code is None else f"\x1b[{code}m{text}{RESET}"


def palette[K](defaults: dict[K, Any], overrides: Any) -> dict[K, Any]:
    """``defaults``, with any valid colour ``overrides`` gives for the same keys.

    For colours a person sets in a plugin's config: a key the plugin does not
    use, or a value that is not a colour, is ignored rather than failing.
    """
    if not isinstance(overrides, dict):
        return dict(defaults)

    return {
        key: overrides[key] if sgr(overrides.get(key)) is not None else color
        for key, color in defaults.items()
    }


def level_for(used_percent: float, warning: float = 75, critical: float = 90) -> str:
    """Maps a percentage to a severity name."""

    if used_percent >= critical:
        return "critical"

    if used_percent >= warning:
        return "warning"

    return "normal"
