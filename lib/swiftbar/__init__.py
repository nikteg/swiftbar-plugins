"""A small toolkit for writing SwiftBar plugins in Python.

The plugins in this repo are stdlib-only and are launched by SwiftBar through
a PEP 723 shebang, so this package never needs installing. ``plugins/swiftbar``
symlinks here, which puts it in each plugin's own directory — the one place
Python adds to ``sys.path`` by itself — so a plugin just imports it.

    from swiftbar import Item, Title, run

    def build():
        return [Title("Hello"), Item("A row", href="https://example.com")]

    raise SystemExit(run(build, name="Example"))
"""

from .ansi import RESET, colorize, level_for
from .dates import parse_date, relative
from .meters import bar, clamp_percent, compact_number, round_half_up
from .notify import notify
from .output import escape, escape_strict, render
from .plugin import clean_error, is_action, run
from .shell import is_running, which
from .ui import Item, Refresh, Separator, Title, Unavailable

__all__ = [
    "Item",
    "Refresh",
    "Separator",
    "Title",
    "Unavailable",
    "RESET",
    "bar",
    "clamp_percent",
    "clean_error",
    "colorize",
    "compact_number",
    "escape",
    "escape_strict",
    "render",
    "is_action",
    "is_running",
    "level_for",
    "notify",
    "parse_date",
    "relative",
    "round_half_up",
    "run",
    "which",
]
