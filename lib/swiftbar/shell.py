"""Locating and running external commands from a GUI context."""

from __future__ import annotations

import os
import shutil
import subprocess

#: SwiftBar inherits a minimal PATH from launchd, so the usual places for
#: user-installed binaries are missing unless they are added back.
EXTRA_PATH = ("/opt/homebrew/bin", "/usr/local/bin", os.path.expanduser("~/.bin"))


def search_path() -> str:
    parts = [*EXTRA_PATH, *os.environ.get("PATH", "").split(os.pathsep)]
    seen: dict[str, None] = {}

    for part in parts:
        if part:
            seen.setdefault(part, None)

    return os.pathsep.join(seen)


def which(name: str) -> str | None:
    return shutil.which(name, path=search_path())


def is_running(process_name: str) -> bool:
    return (
        subprocess.run(
            ["/usr/bin/pgrep", "-x", process_name], capture_output=True
        ).returncode
        == 0
    )


def run(command: list[str], timeout: float = 10.0) -> str:
    """Runs a command and returns stdout, raising with stderr on failure."""
    result = subprocess.run(
        command,
        capture_output=True,
        timeout=timeout,
        env={**os.environ, "PATH": search_path()},
    )

    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()

        raise RuntimeError(detail or f"{command[0]} failed")

    return result.stdout.decode("utf-8", "replace")
