"""A CI run from any source, and what the menu derives from a list of them."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime

from swiftbar_lib import state
from swiftbar_lib.components import SOFT_COLORS
from swiftbar_lib.errors import clean_error
from swiftbar_lib.http import gather

#: How much of a failed log to show, and of how many failed jobs per run.
LOG_LINES = 10
MAX_FAILED_JOBS = 3

FAILURES_FILE = "failures.json"

#: The colour of each state's squircle, before a plugin's ``colors`` setting.
DEFAULT_COLORS = {
    "running": SOFT_COLORS["warning"],
    "success": SOFT_COLORS["normal"],
    "failure": SOFT_COLORS["critical"],
    "other": SOFT_COLORS["unknown"],
}

ANSI_CODE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


@dataclass(frozen=True)
class Run:
    """A GitHub Actions run or a Buildkite build; the menu treats both alike."""

    id: str
    attempt: int
    #: ``owner/name`` for a GitHub repo, otherwise a Buildkite pipeline slug.
    repo: str
    workflow: str
    #: What makes two runs the same workflow: its file, or its pipeline slug.
    workflow_key: str
    workflow_url: str | None
    sha: str
    commit_url: str | None
    #: The commit message's first line, and all of it.
    title: str
    message: str
    #: Who wrote the commit, and when, where the source says.
    author: str
    committed_at: datetime | None
    number: int
    branch: str
    event: str
    actor: str
    #: One of running, success, failure, other.
    state: str
    #: The source's own word for it, for the submenu: in_progress, canceled.
    status: str
    url: str
    created_at: datetime
    started_at: datetime
    finished_at: datetime | None
    #: What "Show failed log in Terminal" runs, when there is a failure.
    log_command: tuple[str, ...] = ()

    def elapsed(self, now: datetime) -> float:
        """Seconds it has been running, or took once it finished."""
        return ((self.finished_at or now) - self.started_at).total_seconds()

    @property
    def commit(self) -> tuple[str, str]:
        """What groups runs together: the repo and the commit they ran on."""
        return (self.repo, self.sha or self.id)


@dataclass(frozen=True)
class FailedJob:
    name: str
    step: str
    url: str
    log: list[str]


#: What a failed run's log said, or why it could not be read.
Diagnosis = list[FailedJob] | str


@dataclass(frozen=True)
class Latest:
    runs: list[Run] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def newest(runs: list[Run]) -> list[Run]:
    return sorted(runs, key=lambda run: run.created_at, reverse=True)


def first_commits(runs: list[Run], count: int) -> list[Run]:
    """Every run of the ``count`` newest commits, none of them cut short."""
    commits = list(grouped(runs, lambda run: run.commit).values())[:count]

    return [run for commit in commits for run in commit]


def grouped[K](runs: list[Run], key: Callable[[Run], K]) -> dict[K, list[Run]]:
    """Groups runs by ``key``, groups ordered by their newest run."""
    groups: dict[K, list[Run]] = {}

    for run in runs:
        groups.setdefault(key(run), []).append(run)

    return groups


def overall(runs: list[Run]) -> str:
    """The state of a group of runs: the worst of each workflow's latest."""
    latest = grouped(runs, lambda run: run.workflow_key or run.workflow)
    states = {workflow_runs[0].state for workflow_runs in latest.values()}

    return next(
        (state for state in ("failure", "running", "success") if state in states),
        "other",
    )


def duration(seconds: float) -> str:
    seconds = max(0, int(seconds))

    if seconds < 60:
        return f"{seconds}s"

    hours, minutes = divmod(seconds // 60, 60)

    if hours == 0:
        return f"{minutes}m"

    if hours < 24:
        return f"{hours}h {minutes}m"

    return f"{hours // 24}d {hours % 24}h"


def diagnose(
    plugin: str, runs: list[Run], read: Callable[[Run], list[FailedJob]]
) -> dict[str, Diagnosis]:
    """What each failed run's log said, read once per run attempt.

    A finished run's log never changes, so what ``read`` found is kept in the
    plugin's cache directory and only runs not seen before cost any calls.
    Only the runs passed in are kept, so the file does not grow.
    """
    cached = state.load(plugin, FAILURES_FILE)

    def lookup(run: Run) -> Diagnosis:
        try:
            return [FailedJob(**job) for job in cached[f"{run.id}/{run.attempt}"]]
        except (KeyError, TypeError):
            pass

        try:
            return read(run)
        except (RuntimeError, TimeoutError, ValueError) as error:
            return clean_error(error)

    diagnoses = dict(zip((run.id for run in runs), gather(runs, lookup), strict=True))
    state.save(
        plugin,
        {
            f"{run.id}/{run.attempt}": [asdict(job) for job in diagnoses[run.id]]
            for run in runs
            if isinstance(diagnoses[run.id], list)
        },
        FAILURES_FILE,
    )

    return diagnoses
