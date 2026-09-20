#!/usr/bin/env -S /opt/homebrew/bin/uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
# <swiftbar.title>Kubecontext</swiftbar.title>
# <swiftbar.author>nikteg</swiftbar.author>
# <swiftbar.author.github>nikteg</swiftbar.author.github>
# <swiftbar.desc>Show and switch the active kubeconfig context</swiftbar.desc>
# <swiftbar.dependencies>uv,kubectl</swiftbar.dependencies>
"""Show and switch the active kubeconfig context.

Shows
    Menu bar: the active context, trimmed at the first ``/`` by default so a
    long ARN-style name stays readable.
    Dropdown: every context, ● marking the active one. Clicking one runs
    ``kubectl config use-context`` and refreshes.

Configure
    Edit the call at the bottom of this file.
      short_names  False to show the full context name in the menu bar.

Requires
    ``kubectl`` on PATH. SwiftBar inherits a minimal PATH from launchd, so the
    toolkit also searches Homebrew's directories and ~/.bin; a missing kubectl
    is reported in the dropdown rather than failing silently.

Refresh
    Every minute, from the ``1m`` in this file's name. Rename to change it.
"""

from sources import kubectl
from swiftbar.output import render
from swiftbar.plugin import guard
from swiftbar.ui import Item, Node, Title, Unavailable


def Context(context: kubectl.Context, binary: str) -> Node:
    return Item(
        f"{'●' if context.active else '○'} {context.name}",
        refresh=True,
        terminal=False,
        bash=binary,
        params=["config", "use-context", context.name],
    )


def Kubecontext(short_names: bool) -> Node:
    binary = kubectl.binary()

    if binary is None:
        return Unavailable("⎈ —", "kubectl not found on PATH")

    contexts = kubectl.contexts(binary)
    active = next((c for c in contexts if c.active), None)

    return [
        Title(
            "⎈ no context"
            if active is None
            else (active.short_name if short_names else active.name)
        ),
        [Context(context, binary) for context in contexts],
    ]


if __name__ == "__main__":
    guard(name="Kubecontext", icon="⎈")
    print(render(Kubecontext(short_names=True)))
