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


from swiftbar.output import Menu
from swiftbar.plugin import run as run_plugin
from swiftbar.shell import (
    is_running,
    which,
)
from swiftbar.shell import run as run_command


def speaker_icon(volume: int) -> str:
    if volume <= 23:
        return "🔈"

    if volume <= 33:
        return "🔉"

    return "🔊"


def run(presets: tuple[int, ...] = (20, 30, 50, 70)) -> int:
    def build(menu: Menu) -> None:
        if not is_running("Spotify"):
            menu.unavailable("Spotify", "Spotify not running")

            return

        binary = which("spotify_volume")

        if binary is None:
            menu.unavailable("Spotify", "spotify_volume not found on PATH")

            return

        volume = (int(run_command([binary, "get"]).strip()) + 5) // 10 * 10
        menu.title(f"{speaker_icon(volume)} {volume}%")
        menu.sep()

        for preset in presets:
            menu.item(
                f"{preset}%",
                bash=binary,
                params=["set", str(preset)],
                terminal=False,
                refresh=True,
                checked=preset == volume,
            )

    return run_plugin(build, name="Spotify volume", icon="🔇")


if __name__ == "__main__":
    raise SystemExit(run(presets=(20, 30, 50, 70)))
