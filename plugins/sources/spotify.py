"""Spotify's volume, read and set through the `spotify_volume` helper."""

from __future__ import annotations

from swiftbar_lib.shell import is_running, run, which

PROCESS = "Spotify"
HELPER = "spotify_volume"


def running() -> bool:
    return is_running(PROCESS)


def binary() -> str | None:
    return which(HELPER)


def volume(helper: str) -> int:
    """The current volume, rounded to the nearest ten so labels do not jitter."""
    return (int(run([helper, "get"]).strip()) + 5) // 10 * 10


def speaker_icon(level: int) -> str:
    if level <= 23:
        return "🔈"

    if level <= 33:
        return "🔉"

    return "🔊"
