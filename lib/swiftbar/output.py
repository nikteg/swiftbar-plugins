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
_UNSAFE_TEXT = re.compile(r"[\x00-\x1f\x7f-\x9f|]+")

#: Attribute values are quoted, so only the quoting characters need escaping.
_NEEDS_QUOTING = re.compile(r"[\s\"'\\|]")


def escape(text: str) -> str:
    """Makes arbitrary text safe to use as a menu row's label."""

    return _UNSAFE_TEXT.sub(" ", str(text)).strip()


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
        if value is None or value is False:
            continue  # Absent and off are the same thing to SwiftBar.

        if key == "params":
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


class Item:
    """A menu row. Adding to it nests a submenu underneath."""

    def __init__(self, text: str, depth: int, lines: list[str], **attrs: Any) -> None:
        self._depth = depth
        self._lines = lines
        self._lines.append(format_line(text, depth, **attrs))

    def item(self, text: str, **attrs: Any) -> Item:
        return Item(text, self._depth + 1, self._lines, **attrs)

    def sep(self) -> None:
        self._lines.append("--" * (self._depth + 1) + SEPARATOR)

    def lines(self, texts, **attrs: Any) -> None:
        for text in texts:
            self.item(text, **attrs)


class Menu:
    """Collects the menu bar line(s) and the dropdown, then renders once."""

    def __init__(self) -> None:
        self._titles: list[str] = []
        self._lines: list[str] = []

    def title(self, text: str, **attrs: Any) -> None:
        """Adds a menu bar line. Several rotate in SwiftBar."""
        self._titles.append(format_line(text, 0, **attrs))

    def item(self, text: str, **attrs: Any) -> Item:
        return Item(text, 0, self._lines, **attrs)

    def sep(self) -> None:
        # Collapse repeats so callers can separate sections unconditionally.
        if self._lines and self._lines[-1] != SEPARATOR:
            self._lines.append(SEPARATOR)

    def lines(self, texts, **attrs: Any) -> None:
        for text in texts:
            self.item(text, **attrs)

    def raw(self, line: str) -> None:
        """Appends an already-formatted line, for output the API cannot express."""
        self._lines.append(line)

    def unavailable(self, title: str, reason: str, **attrs: Any) -> Item:
        """The "cannot show anything right now" menu, which most plugins need.

        A missing binary or an empty API response is an ordinary state, not a
        failure, so it gets a plain menu rather than the error styling.
        """
        self.title(title)
        self.sep()

        return self.item(reason, **attrs)

    def refresh_item(self, label: str = "Refresh") -> Item:
        return self.item(label, refresh=True)

    def render(self) -> str:
        titles = self._titles or ["?"]
        body = self._lines

        while body and body[-1] == SEPARATOR:
            body.pop()

        return "\n".join([*titles, SEPARATOR, *body]) if body else "\n".join(titles)

    def print(self) -> None:
        print(self.render())
