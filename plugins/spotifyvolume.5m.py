#!/usr/bin/env -S /opt/homebrew/bin/uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
# <swiftbar.title>Spotify volume</swiftbar.title>
# <swiftbar.author>nikteg</swiftbar.author>
# <swiftbar.author.github>nikteg</swiftbar.author.github>
# <swiftbar.desc>Read and set Spotify's volume</swiftbar.desc>
# <swiftbar.dependencies>uv,spotify_volume</swiftbar.dependencies>
"""Read and set Spotify's volume.

Shows
    Menu bar: a speaker icon scaled to the level, and the volume rounded to
    the nearest ten so the label does not jitter on every refresh.
    Dropdown: the presets, with the current one checked. Clicking one sets the
    volume and refreshes.
    Nothing but "Spotify not running" when Spotify is closed.

Configure
    Edit the menu at the bottom of this file. Each preset is one row, so
    adding or changing one is a line.

Requires
    The ``spotify_volume`` helper on PATH, which this plugin shells out to for
    both ``get`` and ``set``.

Refresh
    Every 5 minutes, from the ``5m`` in this file's name. Clicking a preset
    refreshes immediately, so the interval only matters for outside changes.
"""

from swiftbar_lib.components import Action
from swiftbar_lib.output import show
from swiftbar_lib.plugin import guard
from swiftbar_lib.shell import is_running, run, which
from swiftbar_lib.ui import Item, Node, Title

PROCESS = "Spotify"
HELPER = "spotify_volume"


def volume(helper: str) -> int:
    """The current volume, rounded to the nearest ten so labels do not jitter."""
    return (int(run([helper, "get"]).strip()) + 5) // 10 * 10


def speaker_icon(level: int) -> str:
    if level <= 23:
        return "🔈"

    if level <= 33:
        return "🔉"

    return "🔊"


def Preset(preset: int, current: int, helper: str) -> Node:
    """One volume row, checked when it matches the current level."""
    return Action(f"{preset}%", helper, "set", preset, checked=preset == current)


if __name__ == "__main__":
    guard(name="Spotify volume", icon="🔇")

    running = is_running(PROCESS)
    helper = which(HELPER) if running else None
    level = volume(helper) if helper else None

    show(
        Title(f"{speaker_icon(level)} {level}%")
        if level is not None
        else Title("Spotify"),
        [
            Preset(20, level, helper),
            Preset(30, level, helper),
            Preset(50, level, helper),
            Preset(70, level, helper),
        ]
        if helper
        else Item("Spotify not running" if not running else f"{HELPER} not on PATH"),
    )
