"""The components both CI plugins' menus are made of.

Each takes a ``View``: what every row needs besides its own runs — the time,
the plugin's colours, and what the failed logs said — so a component's
arguments are its data, not the same three values passed down every level.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from datetime import datetime

from swiftbar_lib.ansi import colorize
from swiftbar_lib.components import MONOSPACE, Action, Link, Squircles, squircle
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


def Squares(runs: list[Run], colors: dict[str, str | int], count: int) -> Node:
    """The menu bar: the ``count`` newest commits, a squircle for each run on one.

    The runs of a commit sit together with a line between commits, and a
    commit is never cut short.
    """
    commits = grouped(first_commits(runs, count), lambda run: run.commit).values()

    return Squircles(
        [[colors[run.state] for run in commit] for commit in commits]
        or [[colors["other"]]]
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
        f"{escape_strict(run.workflow)} "
        + colorize(f"#{run.number} · {when}", "muted"),
        Item(f"{run.event} by {run.actor}", font=MONOSPACE),
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
        ansi=True,
        href=run.url,
        image=squircle(view.colors[run.state]),
        font=MONOSPACE,
        length=70,
    )


#: Menus do not wrap, so a message's long lines are wrapped to this many
#: characters in the submenu.
MESSAGE_WIDTH = 80


def message_lines(message: str) -> list[str | None]:
    """A commit message as submenu rows: lines wrapped, None between paragraphs.

    A line starting with a dash would read as a deeper submenu level, so a
    bullet becomes • and any other leading dash a hyphen that is not one.
    """
    rows: list[str | None] = []

    for line in message.strip().splitlines():
        if not line.strip():
            if rows and rows[-1] is not None:
                rows.append(None)
            continue

        if line.lstrip().startswith(("- ", "* ")):
            line = "• " + line.lstrip()[2:]
        elif line.startswith("-"):
            line = "\u2010" + line[1:]

        rows.extend(textwrap.wrap(line, MESSAGE_WIDTH) or [line])

    return rows


def CommitDetails(head: Run, now: datetime) -> Node:
    """What a commit's submenu says about it before its message."""
    committed = (
        f"Committed {duration((now - head.committed_at).total_seconds())} ago"
        f" · {head.committed_at.astimezone():%a %d %b %H:%M}"
        if head.committed_at
        else None
    )

    return [
        Item(head.sha, font=MONOSPACE) if head.sha else None,
        Item(
            " · ".join(part for part in (head.branch, head.author) if part),
            font=MONOSPACE,
        )
        if head.branch or head.author
        else None,
        Item(committed, font=MONOSPACE) if committed else None,
    ]


def Commit(runs: list[Run], view: View) -> Node:
    """A commit's heading, over the runs it triggered.

    The heading leads with the repo's name, since commits from different
    repos sit side by side, as they do in the menu bar, and ends with the
    message's first line, cut to fit. Its submenu has the full hash, author
    and time, the whole message, and a link to the
    commit, since a row with a submenu opens it on click rather than
    following its own link.
    """
    head = runs[0]
    name = head.repo.rpartition("/")[2]
    details = " · ".join(
        part for part in (head.sha[:7], head.branch, head.title) if part
    )

    return [
        Item(
            f"{escape_strict(name)} "
            + colorize(f"· {escape_strict(details)}", "muted"),
            CommitDetails(head, view.now),
            Separator(),
            [
                Item(line, font=MONOSPACE) if line is not None else Separator()
                for line in message_lines(head.message)
            ],
            Separator(),
            Link("Open commit", head.commit_url) if head.commit_url else None,
            # SwiftBar attributes cannot hold a |, so no shell pipe to pbcopy.
            Action(
                "Copy hash",
                "/usr/bin/osascript",
                "-e",
                f'set the clipboard to "{head.sha}"',
                refresh=False,
            )
            if head.sha
            else None,
            ansi=True,
            image=squircle(view.colors[overall(runs)]),
            font=MONOSPACE,
            length=70,
            href=head.commit_url,
        ),
        [WorkflowRun(run, view) for run in runs],
    ]


def Commits(runs: list[Run], view: View, in_bar: int) -> Node:
    """The dropdown: one group per commit, in the menu bar's order.

    Newest first across every repo, a separator between commits where the
    menu bar has its line. The ``in_bar`` commits the bar shows are listed
    here one for one, so it is plain which squircle is which; the rest are
    tucked into a submenu of their own below them.
    """
    commits = list(grouped(runs, lambda run: run.commit).values())
    older = commits[in_bar:]

    return [
        [[Commit(commit, view), Separator()] for commit in commits[:in_bar]],
        Item(
            f"More ({len(older)})",
            [[Commit(commit, view), Separator()] for commit in older],
            font=MONOSPACE,
        )
        if older
        else None,
    ]


def Problem(error: str) -> Node:
    return Item(
        colorize(f"⚠ {escape_strict(error)}", "critical"), ansi=True, font=MONOSPACE
    )
