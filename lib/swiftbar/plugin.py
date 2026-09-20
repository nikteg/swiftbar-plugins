"""The entrypoint wrapper every plugin file goes through.

An uncaught exception would otherwise put a stack trace in the menu bar, so a
failing plugin renders a readable error row instead and still exits 0.
"""

from __future__ import annotations

import re
import socket
import sys
from collections.abc import Callable

from .ansi import colorize
from .output import Menu

_COLLAPSE = re.compile(r"[|\r\n]+")
MAX_ERROR_LENGTH = 100


def clean_error(error: BaseException) -> str:
    """One short, pipe-free line describing a failure."""

    if isinstance(error, (TimeoutError, socket.timeout)):
        return "Request timed out"

    text = _COLLAPSE.sub(" ", str(error)).strip()
    # A menu row this long is already unreadable; anything more is noise.
    return (text or error.__class__.__name__)[:MAX_ERROR_LENGTH]


def run(build: Callable[[Menu], None], *, name: str, icon: str = "⚠") -> int:
    """Builds and prints a menu, turning a crash into a visible error row."""
    menu = Menu()

    try:
        build(menu)
    except Exception as error:  # noqa: BLE001 - the menu bar is the error channel
        menu = Menu()  # Discard partial output; a half-drawn menu misleads.
        menu.title(f"{icon} {name}")
        menu.sep()
        menu.item(colorize(clean_error(error), "critical"), ansi=True)
        print(menu.render())

        return 0

    menu.print()

    return 0


def is_action(argument: str, argv: list[str] | None = None) -> bool:
    """True when SwiftBar re-invoked the plugin for a menu action."""

    return argument in (sys.argv[1:] if argv is None else argv)
