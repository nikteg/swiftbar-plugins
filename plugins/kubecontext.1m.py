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


from swiftbar.output import Menu
from swiftbar.plugin import run as run_plugin
from swiftbar.shell import run as run_command
from swiftbar.shell import which


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


def run(short_names: bool = True) -> int:
    def build(menu: Menu) -> None:
        kubectl = which("kubectl")

        if kubectl is None:
            menu.unavailable("⎈ —", "kubectl not found on PATH")

            return

        found = contexts(kubectl)
        active = next((name for name, is_active in found if is_active), None)

        if active is None:
            menu.title("⎈ no context")
        else:
            menu.title(active.partition("/")[0] if short_names else active)

        menu.sep()

        for name, is_active in sorted(found):
            menu.item(
                "{} {}".format("●" if is_active else "○", name),
                refresh=True,
                terminal=False,
                bash=kubectl,
                params=["config", "use-context", name],
            )

    return run_plugin(build, name="Kubecontext", icon="⎈")


if __name__ == "__main__":
    raise SystemExit(run(short_names=True))
