"""The components both CI plugins' menus are made of.

Each takes a ``View``: what every row needs besides its own runs — the time,
the plugin's colours, and what the failed logs said — so a component's
arguments are its data, not the same three values passed down every level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from swiftbar_lib.ansi import colorize
from swiftbar_lib.components import (
    MONOSPACE,
    SQUARE,
    Indicator,
    Indicators,
    Link,
    elbow,
)
from swiftbar_lib.output import escape_strict
from swiftbar_lib.ui import Item, Node, Separator

from .runs import Diagnosis, FailedJob, Run, duration, first_commits, grouped, overall


@dataclass(frozen=True)
class View:
    now: datetime
    #: A colour per state, as ``ansi.palette`` built it from the plugin's config.
    colors: dict[str, str | int]
    #: What each failed run's log said, by run id.
    diagnoses: dict[str, Diagnosis] = field(default_factory=dict)
    #: What the source calls a run and a workflow, for the links.
    nouns: tuple[str, str] = ("run", "workflow")


def Square(run: Run, colors: dict[str, str | int]) -> str:
    return Indicator(colors[run.state], SQUARE)


def Squares(runs: list[Run], colors: dict[str, str | int], count: int) -> Node:
    """The menu bar: the ``count`` newest commits, a square for each run on one.

    The runs of a commit sit side by side, and a commit is never cut short.
    """
    commits = grouped(first_commits(runs, count), lambda run: run.commit).values()

    return Indicators(
        *(
            ["".join(Square(run, colors) for run in commit) for commit in commits]
            or [Indicator(colors["other"], SQUARE)]
        )
    )


def Outcome(run: Run, now: datetime) -> str:
    took = duration(run.elapsed(now))
    words = run.status.replace("_", " ").capitalize()

    match run.state:
        case "running":
            return f"{words} for {took}"
        case "success" if run.status == "blocked":
            return f"Blocked after {took}"
        case "success":
            return f"Succeeded in {took}"
        case "failure" if run.finished_at is None:
            return f"Failing for {took}"
        case "failure":
            return f"Failed in {took}"
        case _:
            return f"{words} after {took}"


def JobFailure(job: FailedJob) -> Node:
    """A failed job and step, linking to it, over the end of its log."""
    where = f"{job.name} › {job.step}" if job.step else job.name

    return [
        Separator(),
        Item(
            colorize(f"✗ {escape_strict(where)}", "critical"),
            ansi=True,
            font=MONOSPACE,
            href=job.url,
        ),
        # The gutter also stops a log line starting with -- from reading as a
        # deeper submenu level.
        [Item(f"│ {line}", font=MONOSPACE, size=11, length=100) for line in job.log],
    ]


def Failure(diagnosis: Diagnosis | None) -> Node:
    if isinstance(diagnosis, str):
        return [Separator(), Problem(f"Could not read the log: {diagnosis}")]

    return [JobFailure(job) for job in diagnosis or []]


def WorkflowRun(run: Run, view: View) -> Node:
    """One run, with its details and links in a submenu."""
    when = (
        f"running {duration(run.elapsed(view.now))}"
        if run.finished_at is None
        else f"{duration((view.now - run.finished_at).total_seconds())} ago"
    )

    return Item(
        elbow(f"{Square(run, view.colors)} {escape_strict(run.workflow)} · {when}"),
        Item(f"#{run.number} · {run.event} by {run.actor}", font=MONOSPACE),
        Item(Outcome(run, view.now), font=MONOSPACE),
        Failure(view.diagnoses.get(run.id)),
        Separator(),
        Link(f"Open {view.nouns[0]}", run.url),
        Link(f"Open {view.nouns[1]}", run.workflow_url) if run.workflow_url else None,
        Item(
            "Show failed log in Terminal",
            bash=run.log_command[0],
            params=list(run.log_command[1:]),
            terminal=True,
        )
        if run.state == "failure" and run.log_command
        else None,
        href=run.url,
        ansi=True,
        font=MONOSPACE,
        length=70,
    )


def Commit(runs: list[Run], view: View) -> Node:
    """A commit's heading, linking to it, over the runs it triggered."""
    head = runs[0]
    heading = " · ".join(
        part for part in (head.sha[:7], head.branch, head.title) if part
    )

    return [
        Item(
            f"{Indicator(view.colors[overall(runs)], SQUARE)} "
            + colorize(escape_strict(heading), "muted"),
            ansi=True,
            font=MONOSPACE,
            length=70,
            href=head.commit_url,
        ),
        [WorkflowRun(run, view) for run in runs],
    ]


def Repo(repo: str, runs: list[Run], view: View) -> Node:
    return [
        Item(repo, font=MONOSPACE, size=13, href=runs[0].repo_url),
        [
            Commit(commit, view)
            for commit in grouped(runs, lambda run: run.commit).values()
        ],
        Separator(),
    ]


def Problem(error: str) -> Node:
    return Item(
        colorize(f"⚠ {escape_strict(error)}", "critical"), ansi=True, font=MONOSPACE
    )
