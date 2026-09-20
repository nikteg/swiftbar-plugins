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
from swiftbar_lib.output import render
from swiftbar_lib.plugin import guard
from swiftbar_lib.ui import Item, Node, Title


def Context(context: kubectl.Context, binary: str) -> Node:
    """One switchable row. Clicking it runs kubectl and refreshes the menu."""
    return Item(
        f"{'●' if context.active else '○'} {context.name}",
        refresh=True,
        terminal=False,
        bash=binary,
        params=["config", "use-context", context.name],
    )


if __name__ == "__main__":
    guard(name="Kubecontext", icon="⎈")

    short_names = True

    binary = kubectl.binary()
    contexts = kubectl.contexts(binary) if binary else []
    active = next((context for context in contexts if context.active), None)

    print(
        render(
            [
                Title(active.short_name if short_names else active.name)
                if active
                else Title("⎈ —"),
                [Context(context, binary) for context in contexts]
                or Item(
                    "kubectl not found on PATH" if binary is None else "No contexts"
                ),
            ]
        )
    )
