"""macOS notifications.

AppleScript string literals need their own escaping; interpolating a title
straight into the script breaks on any quote or backslash it contains.
"""

from __future__ import annotations

import subprocess


def _applescript_string(text: str) -> str:
    return '"{}"'.format(text.replace("\\", "\\\\").replace('"', '\\"'))


def notify(title: str, message: str = "", subtitle: str = "") -> None:
    body = _applescript_string(message)
    heading = _applescript_string(title)
    script = f"display notification {body} with title {heading}"

    if subtitle:
        script += f" subtitle {_applescript_string(subtitle)}"

    subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True)
