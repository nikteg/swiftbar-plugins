"""Reusable components, built from the node types in ``ui``.

``ui`` holds the primitives a menu is made of; these are the rows that turn up
in plugin after plugin, so they live here rather than being rewritten with
slightly different attributes each time.
"""

from __future__ import annotations

from typing import Any

from .ansi import colorize, level_for
from .meters import BAR_WIDTH, bar, round_half_up
from .output import escape_strict
from .ui import Item

MONOSPACE = "Menlo"


def Link(text: str, url: str, **attrs: Any) -> Item:
    """A row that opens a URL."""
    return Item(text, href=url, **attrs)


def Action(
    text: str, command: str, *arguments: Any, refresh: bool = True, **attrs: Any
) -> Item:
    """A row that runs a command without opening a Terminal, then refreshes."""
    return Item(
        text,
        bash=command,
        params=[str(argument) for argument in arguments],
        terminal=False,
        refresh=refresh,
        **attrs,
    )


def Meter(
    label: str,
    percent: float,
    detail: str = "",
    width: int = BAR_WIDTH,
    font: str = MONOSPACE,
) -> Item:
    """A labelled progress bar, coloured green/amber/red by how full it is."""
    used = int(round_half_up(percent))
    # Escaped before the colour codes go on, so provider text cannot forge them.
    text = escape_strict(f"{label}: {bar(used, width)} {used}% used{detail}")

    return Item(colorize(text, level_for(used)), ansi=True, font=font)
