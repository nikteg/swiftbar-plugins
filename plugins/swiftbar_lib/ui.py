"""A declarative menu: components are functions that return nodes.

A plugin describes what the menu *is* for the current data rather than issuing
a sequence of calls that build one up. Nothing mutates, so a component is a
plain function of its inputs, reusable across plugins and testable by asserting
on the tree instead of on rendered text.

    def Post(post) -> Node:
        return Item(
            f"🔥 {post['score']} - {post['title']}",
            Item("💬 Comments", href=post["hn_url"]),
            href=post["url"],
        )

    def build() -> Node:
        return [Title(f"HN ({len(posts)})"), [Post(p) for p in posts]]

Children are positional, attributes are keyword. A list is a fragment and is
flattened, ``None`` renders nothing so ``x if cond else None`` works, and a
bare string is shorthand for ``Item(string)``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class Title:
    """A menu bar line. Several of them rotate in SwiftBar.

    Variadic, so a bar assembled from segments needs no join at the call site.
    """

    __slots__ = ("text", "attrs")

    def __init__(self, *parts: str, separator: str = " ", **attrs: Any) -> None:
        self.text = separator.join(parts)
        self.attrs = attrs

    def __repr__(self) -> str:
        return f"Title({self.text!r})"


class Item:
    """A dropdown row. Positional children become its submenu."""

    __slots__ = ("text", "children", "attrs")

    def __init__(self, text: str, *children: Node, **attrs: Any) -> None:
        self.text = text
        self.children = children
        self.attrs = attrs

    def __repr__(self) -> str:
        return f"Item({self.text!r}, {len(self.children)} children)"


class Separator:
    """A divider. Renders at whatever depth it appears."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "Separator()"


Node = Title | Item | Separator | str | None | Iterable["Node"]


def flatten(node: Node) -> list[Title | Item | Separator]:
    """Resolves fragments, drops ``None``, and promotes bare strings to items."""
    if node is None:
        return []

    if isinstance(node, (Title, Item, Separator)):
        return [node]

    if isinstance(node, str):
        return [Item(node)]

    if isinstance(node, Iterable):
        return [child for entry in node for child in flatten(entry)]

    raise TypeError(f"not a menu node: {node!r}")


def Refresh(label: str = "Refresh") -> Item:
    return Item(label, refresh=True)
