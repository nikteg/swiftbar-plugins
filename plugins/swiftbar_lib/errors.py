"""Turning an exception into something that fits on a menu row.

This is for a failure a plugin expects and wants to show — one provider of
several being unreachable, say. A plugin that fails outright does not catch
anything: SwiftBar surfaces a non-zero exit and whatever went to stderr.
"""

from __future__ import annotations

import re
import socket

_COLLAPSE = re.compile(r"[|\r\n]+")

#: A menu row this long is already unreadable; anything more is noise.
MAX_ERROR_LENGTH = 100


def clean_error(error: BaseException) -> str:
    """One short, pipe-free line describing a failure."""
    if isinstance(error, (TimeoutError, socket.timeout)):
        return "Request timed out"

    text = _COLLAPSE.sub(" ", str(error)).strip()

    return (text or error.__class__.__name__)[:MAX_ERROR_LENGTH]
