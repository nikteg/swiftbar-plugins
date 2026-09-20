"""kubeconfig contexts, read through the kubectl binary."""

from __future__ import annotations

from dataclasses import dataclass

from swiftbar_lib.shell import run, which


@dataclass(frozen=True)
class Context:
    name: str
    active: bool

    @property
    def short_name(self) -> str:
        """Trims at the first ``/``, which keeps an ARN-style name readable."""
        return self.name.partition("/")[0]


def binary() -> str | None:
    return which("kubectl")


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
