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

from dataclasses import dataclass

from swiftbar_lib.components import Action
from swiftbar_lib.output import show
from swiftbar_lib.plugin import guard
from swiftbar_lib.shell import run, which
from swiftbar_lib.ui import Item, Node, Title


@dataclass(frozen=True)
class Context:
    name: str
    active: bool

    @property
    def short_name(self) -> str:
        """Trims at the first ``/``, which keeps an ARN-style name readable."""
        return self.name.partition("/")[0]


def contexts(kubectl: str) -> list[Context]:
    """Every context, sorted by name. kubectl marks the active one with ``*``."""
    found = []

    for line in run([kubectl, "config", "get-contexts", "--no-headers"]).splitlines():
        columns = line.split()

        if not columns:
            continue

        if columns[0] == "*":
            found.append(Context(columns[1], True))
        else:
            found.append(Context(columns[0], False))

    return sorted(found, key=lambda context: context.name)


def Switch(context: Context, kubectl: str) -> Node:
    """One switchable row; clicking it selects that context and refreshes."""
    return Action(
        f"{'●' if context.active else '○'} {context.name}",
        kubectl,
        "config",
        "use-context",
        context.name,
    )


if __name__ == "__main__":
    guard(name="Kubecontext", icon="⎈")

    short_names = True

    kubectl = which("kubectl")
    found = contexts(kubectl) if kubectl else []
    active = next((context for context in found if context.active), None)

    show(
        Title(active.short_name if short_names else active.name)
        if active
        else Title("⎈ —"),
        [Switch(context, kubectl) for context in found]
        or Item("kubectl not found on PATH" if kubectl is None else "No contexts"),
    )
