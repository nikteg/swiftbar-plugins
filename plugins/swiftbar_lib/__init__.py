"""A small toolkit for writing SwiftBar plugins in Python.

The plugins in this repo are stdlib-only and are launched by SwiftBar through
a PEP 723 shebang, so this package never needs installing. It sits in the same
directory as the plugin files, which is the one place Python puts on
``sys.path`` by itself, so a plugin just imports it.

    from swiftbar_lib import Item, Title, show

    if __name__ == "__main__":
        show(Title("Hello"), Item("A row", href="https://example.com"))
"""

from .ansi import RESET, colorize, level_for
from .components import Action, Link, Meter
from .dates import parse_date, relative
from .errors import clean_error
from .meters import bar, clamp_percent, compact_number, round_half_up
from .notify import notify
from .output import escape, escape_strict, render, show
from .shell import is_running, which
from .ui import Item, Refresh, Separator, Title

__all__ = [
    "Meter",
    "Link",
    "Action",
    "Item",
    "Refresh",
    "Separator",
    "Title",
    "RESET",
    "bar",
    "clamp_percent",
    "clean_error",
    "colorize",
    "compact_number",
    "escape",
    "escape_strict",
    "render",
    "show",
    "is_running",
    "level_for",
    "notify",
    "parse_date",
    "relative",
    "round_half_up",
    "which",
]
