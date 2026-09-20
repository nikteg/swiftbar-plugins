"""Menu construction and SwiftBar's line format.

Every plugin used to build these strings by hand, which is where the escaping
bugs live: a `|` anywhere in a title silently truncates the row, because
SwiftBar splits the text from its attributes on the first pipe.
"""

from __future__ import annotations

import re
from typing import Any

SEPARATOR = "---"

#: Control characters and pipes both break the line format, so they go.
#: ESC is spared, because a row with ansi=true carries colour codes.
_UNSAFE_TEXT = re.compile(r"[\x00-\x1a\x1c-\x1f\x7f-\x9f|]+")
_ALL_CONTROL_OR_PIPE = re.compile(r"[\x00-\x1f\x7f-\x9f|]+")

#: Attribute values are quoted, so only the quoting characters need escaping.
_NEEDS_QUOTING = re.compile(r"[\s\"'\\|]")


def escape(text: str) -> str:
    """Makes text safe as a row label, keeping any ANSI colour it carries."""

    return _UNSAFE_TEXT.sub(" ", str(text)).strip()


def escape_strict(text: str) -> str:
    """As ``escape``, but also strips ESC. For text from outside the plugin."""

    return _ALL_CONTROL_OR_PIPE.sub(" ", str(text)).strip()


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"

    text = str(value)

    if not text or _NEEDS_QUOTING.search(text):
        return '"{}"'.format(text.replace("\\", "\\\\").replace('"', '\\"'))

    return text


def format_attrs(attrs: dict[str, Any]) -> str:
    """Renders keyword attributes as SwiftBar's ``key=value`` trailer.

    ``params`` is expanded into ``param1..paramN`` so callers can pass a plain
    argument list instead of numbering shell arguments themselves.
    """
    pairs: list[str] = []

    for key, value in attrs.items():
        if value is None:
            continue  # Only None means "leave this attribute out".

        if key == "params":
            # A bare string is iterable, so it would expand to one param per
            # character rather than failing.
            if isinstance(value, (str, bytes)):
                raise TypeError("params must be a sequence of arguments, not a string")

            pairs.extend(
                f"param{index}={_value(argument)}"
                for index, argument in enumerate(value, start=1)
            )
            continue

        pairs.append(f"{key}={_value(value)}")

    return " ".join(pairs)


def format_line(text: str, depth: int = 0, **attrs: Any) -> str:
    """One menu line: submenu prefix, escaped label, then attributes."""
    line = "--" * depth + escape(text)
    trailer = format_attrs(attrs)

    return f"{line} | {trailer}" if trailer else line


def render(*node) -> str:
    """Renders a node tree as SwiftBar expects: titles, ``---``, then the body.

    Variadic, so a menu reads as a list of rows rather than a list argument.
    """
    from .ui import Separator, Title, flatten

    nodes = flatten(list(node))
    titles = [n for n in nodes if isinstance(n, Title)]
    body: list[str] = []

    def emit(entries, depth: int) -> None:
        for entry in entries:
            if isinstance(entry, Title):
                if depth:
                    raise ValueError(
                        f"Title({entry.text!r}) is nested in a submenu; "
                        "the menu bar only takes top-level titles"
                    )

                continue

            if isinstance(entry, Separator):
                line = "--" * depth + SEPARATOR
                # Collapse repeats so a component can separate unconditionally.
                if body and body[-1] != line:
                    body.append(line)
                continue

            body.append(format_line(entry.text, depth, **entry.attrs))
            emit(flatten(entry.children), depth + 1)

    emit(nodes, 0)

    while body and body[-1].lstrip("-") == "":
        body.pop()

    head = [format_line(t.text, 0, **t.attrs) for t in titles] or ["?"]

    return "\n".join([*head, SEPARATOR, *body]) if body else "\n".join(head)


def show(*node) -> None:
    """Writes a rendered tree to stdout, which is where SwiftBar reads it.

    Separate from ``render`` rather than a flag on it: a plugin only ever
    wants it printed, and a test only ever wants the string, so a boolean
    deciding between returning and printing would just be two functions
    sharing a name.
    """
    print(render(*node))
