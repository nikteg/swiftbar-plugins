"""The error boundary a plugin installs before it renders.

An uncaught exception would otherwise put a stack trace in the menu bar, one
traceback line per menu row. ``guard`` installs an excepthook that prints a
readable error menu instead, which lets a plugin render inline:

    if __name__ == "__main__":
        guard(name="Pollen", icon="🌿")
        print(render(Pollen(city="Göteborg")))

A wrapper taking a build callback would do the same job, but only because the
callback is what puts the failure inside its ``try``. The hook removes that
indirection, so a component is called directly where its configuration lives.
"""

from __future__ import annotations

import os
import re
import socket
import sys

from .ansi import colorize
from .output import render
from .ui import Item, Title

_COLLAPSE = re.compile(r"[|\r\n]+")
MAX_ERROR_LENGTH = 100


def clean_error(error: BaseException) -> str:
    """One short, pipe-free line describing a failure."""
    if isinstance(error, (TimeoutError, socket.timeout)):
        return "Request timed out"

    text = _COLLAPSE.sub(" ", str(error)).strip()

    # A menu row this long is already unreadable; anything more is noise.
    return (text or error.__class__.__name__)[:MAX_ERROR_LENGTH]


def error_menu(name: str, error: BaseException, icon: str = "⚠") -> str:
    return render(
        [
            Title(f"{icon} {name}"),
            Item(colorize(clean_error(error), "critical"), ansi=True),
        ]
    )


def guard(*, name: str, icon: str = "⚠") -> None:
    """Replaces the traceback with an error menu for the rest of this run."""

    def hook(kind, error, traceback) -> None:
        print(error_menu(name, error, icon))
        sys.stdout.flush()
        # Exit 0 and skip the default traceback: SwiftBar renders stdout, and a
        # failing refresh should still leave a usable menu.
        os._exit(0)

    sys.excepthook = hook


def is_action(argument: str, argv: list[str] | None = None) -> bool:
    """True when SwiftBar re-invoked the plugin for a menu action."""
    return argument in (sys.argv[1:] if argv is None else argv)
