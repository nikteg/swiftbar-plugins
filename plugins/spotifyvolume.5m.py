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
    Edit the call at the bottom of this file.
      presets  The volume percentages offered in the dropdown.

Requires
    The ``spotify_volume`` helper on PATH, which this plugin shells out to for
    both ``get`` and ``set``.

Refresh
    Every 5 minutes, from the ``5m`` in this file's name. Clicking a preset
    refreshes immediately, so the interval only matters for outside changes.
"""

from sources import spotify
from swiftbar.output import render
from swiftbar.plugin import guard
from swiftbar.ui import Item, Node, Title, Unavailable


def Preset(preset: int, current: int, helper: str) -> Node:
    return Item(
        f"{preset}%",
        bash=helper,
        params=["set", str(preset)],
        terminal=False,
        refresh=True,
        checked=preset == current,
    )


def SpotifyVolume(presets: tuple[int, ...]) -> Node:
    if not spotify.running():
        return Unavailable("Spotify", "Spotify not running")

    helper = spotify.binary()

    if helper is None:
        return Unavailable("Spotify", "spotify_volume not found on PATH")

    level = spotify.volume(helper)

    return [
        Title(f"{spotify.speaker_icon(level)} {level}%"),
        [Preset(preset, level, helper) for preset in presets],
    ]


if __name__ == "__main__":
    guard(name="Spotify volume", icon="🔇")
    print(render(SpotifyVolume(presets=(20, 30, 50, 70))))
