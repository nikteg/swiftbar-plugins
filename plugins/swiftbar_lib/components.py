"""Reusable components, built from the node types in ``ui``.

``ui`` holds the primitives a menu is made of; these are the rows that turn up
in plugin after plugin, so they live here rather than being rewritten with
slightly different attributes each time.
"""

from __future__ import annotations

from typing import Any

from . import config
from .ansi import colorize, level_for, rgb
from .images import SEPARATOR, base64_png, squircles
from .meters import BAR_WIDTH, bar, round_half_up
from .output import escape_strict
from .ui import Item, Title

MONOSPACE = "Menlo"


def elbow(text: str) -> str:
    """Hangs a row off the one above it, indented under a └. Needs ``ansi=True``.

    The └ is coloured, which is also what keeps its indent: a label is
    stripped when rendered, and the colour code in front shields the spaces.
    """
    return f"{colorize('  └', 'muted')} {text}"


#: Status colours for squircles, softer than the macOS system colours ANSI
#: gets: GitHub's own success, attention, danger, accent and muted shades,
#: which read well on both a light and a dark menu bar. Keyed by the same
#: level names as ``ansi.COLORS``, so ``level_for`` picks one.
SOFT_COLORS = {
    "normal": "#3fb950",
    "warning": "#d29922",
    "critical": "#f85149",
    "activity": "#58a6ff",
    "unknown": "#8b949e",
    #: Could not be read at all. Red like critical, since it wants looking
    #: at too; it is drawn as a warning triangle instead of a squircle.
    "error": "#f85149",
}


def _mark(entry: Any) -> Any:
    """A colour, or a (colour, shape) pair, as ``images.squircles`` takes it."""
    if isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[1], str):
        return (rgb(entry[0]) or rgb("unknown"), entry[1])

    return rgb(entry) or rgb("unknown")


def squircle(color: Any, *, shape: str | None = None, indent: bool = False) -> str:
    """A row's ``image=``: one squircle in anything ``ansi.rgb`` reads.

    ``shape="warning"`` draws a warning triangle instead. With ``indent`` it
    starts further in, for a row hanging off the one above.
    """
    mark = _mark((color, shape) if shape else color)

    return base64_png(squircles([[mark]], indent=indent))


def Squircles(
    groups: list[list[Any]], *, gap: float = 2, separators: bool = True
) -> Title:
    """A menu bar of squircles, drawn as an image since ANSI cannot draw them.

    ``groups`` are colours, anything ``ansi.rgb`` reads, or (colour,
    "warning") pairs for a warning triangle instead; with ``separators``
    a thin line sits between groups, otherwise just a wider gap.
    """
    image = squircles(
        [[_mark(entry) for entry in group] for group in groups],
        gap=gap,
        separator=SEPARATOR if separators else None,
    )

    return Title("", image=base64_png(image), dropdown=False)


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
