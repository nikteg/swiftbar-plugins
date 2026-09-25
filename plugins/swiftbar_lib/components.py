"""Reusable components, built from the node types in ``ui``.

``ui`` holds the primitives a menu is made of; these are the rows that turn up
in plugin after plugin, so they live here rather than being rewritten with
slightly different attributes each time.
"""

from __future__ import annotations

from typing import Any

from . import config
from .ansi import colorize, level_for
from .meters import BAR_WIDTH, bar, round_half_up
from .output import escape_strict
from .ui import Item, Title

MONOSPACE = "Menlo"

#: Shapes for ``Indicator``. A plugin picks its own so two status bars side by
#: side are told apart at a glance. Unicode has no filled squircle; the
#: rounded square is an outline.
CIRCLE = "●"
SQUARE = "■"
ROUNDED_SQUARE = "▢"


def elbow(text: str) -> str:
    """Hangs a row off the one above it, indented under a └. Needs ``ansi=True``.

    The └ is coloured, which is also what keeps its indent: a label is
    stripped when rendered, and the colour code in front shields the spaces.
    """
    return f"{colorize('  └', 'muted')} {text}"


def Indicator(color: str | int, shape: str = CIRCLE) -> str:
    """One status mark, in anything ``ansi.sgr`` takes: "critical", 208, "#ff9500"."""
    return colorize(shape, color)


def Indicators(*indicators: str) -> Title:
    """A menu bar of status marks, as ``Indicator`` draws them."""
    return Title(
        *indicators,
        ansi=True,
        symbolize=False,
        font=MONOSPACE,
        size=13,
        dropdown=False,
    )


def Unconfigured(plugin: str, *keys: str) -> Item:
    """A row naming the settings a plugin needs and the file they go in.

    ``plugin`` is the plugin's ``__file__``, as ``config.load`` takes it.
    """
    return Item(f"Set {' and '.join(keys)} in {config.display_path(plugin)}")


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
