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

from swiftbar.output import render
from swiftbar.plugin import guard
from swiftbar.shell import run as run_command
from swiftbar.shell import which
from swiftbar.ui import Item, Node, Title, Unavailable


def contexts(kubectl: str) -> list[tuple[str, bool]]:
    """Returns ``(name, active)`` pairs; kubectl marks the active one with ``*``."""
    output = run_command([kubectl, "config", "get-contexts", "--no-headers"])
    found = []

    for line in output.splitlines():
        columns = line.split()

        if not columns:
            continue

        if columns[0] == "*":
            found.append((columns[1], True))
        else:
            found.append((columns[0], False))

    return found


def Context(name: str, active: bool, kubectl: str) -> Node:
    return Item(
        f"{'●' if active else '○'} {name}",
        refresh=True,
        terminal=False,
        bash=kubectl,
        params=["config", "use-context", name],
    )


def Kubecontext(short_names: bool) -> Node:
    kubectl = which("kubectl")

    if kubectl is None:
        return Unavailable("⎈ —", "kubectl not found on PATH")

    found = contexts(kubectl)
    active = next((name for name, is_active in found if is_active), None)

    return [
        Title(
            "⎈ no context"
            if active is None
            else (active.partition("/")[0] if short_names else active)
        ),
        [Context(name, is_active, kubectl) for name, is_active in sorted(found)],
    ]


if __name__ == "__main__":
    guard(name="Kubecontext", icon="⎈")
    print(render(Kubecontext(short_names=True)))
