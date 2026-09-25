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


#: Roughly what SwiftBar maps each of those codes to (the system colours), for
#: ``rgb``, which needs a colour an image can use.
_NAMED_RGB = {
    "normal": (52, 199, 89),
    "warning": (255, 204, 0),
    "critical": (255, 59, 48),
    "activity": (0, 122, 255),
    "unknown": (142, 142, 147),
    "accent": (175, 82, 222),
    "muted": (142, 142, 147),
}

_HEX = re.compile(r"^#([0-9a-fA-F]{6})$")

#: The channel values of xterm's 6x6x6 colour cube, indexes 16-231.
_CUBE = (0, 95, 135, 175, 215, 255)


def xterm_256(index: int) -> tuple[int, int, int]:
    """What a terminal draws for a 256-colour index from 16 up."""
    if index >= 232:
        return ((index - 232) * 10 + 8,) * 3

    cube = index - 16

    return (_CUBE[cube // 36], _CUBE[cube // 6 % 6], _CUBE[cube % 6])


def swiftbar_256(index: int) -> tuple[int, int, int]:
    """What SwiftBar actually draws for a 256-colour index from 16 up.

    Not xterm's table: SwiftBar divides without flooring and takes blue from
    the wrong digit (its NSColor.colorForAnsi256ColorIndex), so most of the
    cube comes out as some other colour — 203, xterm's soft red, draws
    orange — and no soft green or red is reachable at all. The greys and the
    pure primaries are right.
    """
    if index >= 232:
        return xterm_256(index)

    i = index - 16
    red = i / 36 * 40 + 55 if i / 36 > 1 else 0
    green = i % 36 / 6 * 40 + 55 if i % 36 / 6 > 1 else 0
    blue = i % 36 * 40 + 55 if i % 6 > 1 else 0

    return tuple(round(min(255, channel)) for channel in (red, green, blue))


def nearest_256(red: int, green: int, blue: int) -> int:
    """The 256-colour index whose colour in SwiftBar is closest to an RGB one."""
    return min(
        range(16, 256),
        key=lambda index: sum(
            (a - b) ** 2
            for a, b in zip(swiftbar_256(index), (red, green, blue), strict=True)
        ),
    )


def _hex_rgb(color: str) -> tuple[int, int, int] | None:
    match = _HEX.match(color)

    if match is None:
        return None

    return tuple(int(match.group(1)[i : i + 2], 16) for i in (0, 2, 4))


def rgb(color: Any) -> tuple[int, int, int] | None:
    """A colour ``sgr`` accepts as RGB, for drawing it in an image instead."""
    if isinstance(color, bool):
        return None

    if isinstance(color, int):
        return xterm_256(color) if 16 <= color <= 255 else None

    if not isinstance(color, str):
        return None

    return _NAMED_RGB.get(color) or _hex_rgb(color)


def sgr(color: Any) -> str | None:
    """The escape parameters for a colour, or None when it is not one.

    A colour is a name from ``COLORS``, a 256-colour index, or ``"#rrggbb"``.
    SwiftBar understands 256-colour codes but not 24-bit ones, so hex is
    matched to the closest colour SwiftBar can draw, which is often far off.
    """
    if isinstance(color, bool):
        return None

    if isinstance(color, int):
        return f"38;5;{color}" if 0 <= color <= 255 else None

    if not isinstance(color, str):
        return None

    if color in COLORS:
        return str(COLORS[color])

    parsed = _hex_rgb(color)

    return None if parsed is None else f"38;5;{nearest_256(*parsed)}"


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
