#!/usr/bin/env -S /opt/homebrew/bin/uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
# <swiftbar.title>GitHub Actions</swiftbar.title>
# <swiftbar.author>nikteg</swiftbar.author>
# <swiftbar.author.github>nikteg</swiftbar.author.github>
# <swiftbar.desc>The latest GitHub Actions runs across your repos</swiftbar.desc>
# <swiftbar.dependencies>uv,gh</swiftbar.dependencies>
"""The latest GitHub Actions runs across your repos.

Shows
    Menu bar: one square per run for the newest few, newest first, the runs
    of one commit side by side — orange while it is queued or running, green
    when it succeeded, red when it failed, grey when it was cancelled or
    skipped.
    Dropdown: more of the latest runs, grouped by repo and then by commit.
    Each commit is headed by a square, the worst of each workflow's latest
    run on it, and its short hash, branch and title. Each run's submenu has
    the trigger and duration, and links to the run and to its workflow's
    page. A failed run also names each failed job and step, shows the last
    lines of its log before the error, and offers to open the full failed log
    in Terminal.

Configure
    In ~/.config/swiftbar-plugins/github-actions.json, outside the repo, so
    which repos you watch is never committed. Every key is optional; the
    defaults are at the bottom of this file.
      squares   How many runs get a square in the menu bar. Default 5.
      listed    How many runs the dropdown lists. Default 15.
      repos     ``owner/name`` repos to watch. Empty means the ``discover``
                most recently pushed repos you have access to.
      discover  How many repos to look in when ``repos`` is empty. Default 10.
      exclude   ``owner/name`` repos never to show. Discovery skips past
                them, so it still finds ``discover`` others.
      actor     A login, or ``@me``, to show only runs that person triggered.
      colors    A colour per state — running, success, failure, other — as
                "#rrggbb", an xterm-256 number, or a name such as "warning".
                Unset ones keep the defaults, which follow the menu's ANSI
                palette.

    {"exclude": ["acme/legacy-app"], "colors": {"running": "#ff9500"}}

Source
    ``gh api``, as whichever account ``gh auth status`` shows as active.
    GitHub has no endpoint that lists runs across repos, so one call finds the
    repos and then one per repo, in parallel, fetches its latest runs. At a
    one-minute refresh that is about 660 of the 5000 requests an hour allows.
    A repo that fails (SSO not authorised, Actions disabled) is listed with
    its error instead of failing the run.

    A failed run costs two more calls per failed job, the job list and its
    log, once: a finished run's log does not change, so what was read from it
    is kept in failures.json in the plugin's cache directory, keyed by run and
    attempt. The error is read from the log rather than from check-run
    annotations, which a fine-grained token often cannot read.

Requires
    ``gh``, logged in. A missing one is reported in the dropdown.

Refresh
    Every minute, from the ``1m`` in this file's name. Rename to change it.
"""

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from swiftbar_lib import config, state
from swiftbar_lib.ansi import colorize, palette
from swiftbar_lib.components import (
    MONOSPACE,
    SQUARE,
    Indicator,
    Indicators,
    Link,
    elbow,
)
from swiftbar_lib.data import number_at, object_at, string_at, strings_at
from swiftbar_lib.dates import parse_date
from swiftbar_lib.errors import clean_error
from swiftbar_lib.http import gather
from swiftbar_lib.output import escape_strict, show
from swiftbar_lib.shell import run as run_command
from swiftbar_lib.shell import which
from swiftbar_lib.ui import Item, Node, Refresh, Separator

#: Every status GitHub reports for a run that has not finished.
ACTIVE = {"queued", "in_progress", "waiting", "requested", "pending"}
FAILED = {"failure", "timed_out", "startup_failure"}

PLUGIN = "github-actions"
FAILURES_FILE = "failures.json"

#: How much of a failed log to show, and of how many failed jobs per run.
LOG_LINES = 10
MAX_FAILED_JOBS = 3

_TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ?")
_ANSI_CODE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

#: This plugin's settings from outside the repo; see Configure above.
SETTINGS = config.load(__file__)

#: The colour of each state's square, overridable by ``colors`` in SETTINGS.
COLORS = palette(
    {
        "running": "warning",
        "success": "normal",
        "failure": "critical",
        "other": "unknown",
    },
    object_at(SETTINGS, "colors"),
)


@dataclass(frozen=True)
class Run:
    id: int
    attempt: int
    repo: str
    workflow: str
    sha: str
    title: str
    number: int
    branch: str
    event: str
    actor: str
    status: str
    conclusion: str
    url: str
    workflow_path: str
    created_at: datetime
    started_at: datetime
    updated_at: datetime

    @property
    def state(self) -> str:
        if self.status in ACTIVE:
            return "running"

        if self.conclusion == "success":
            return "success"

        return "failure" if self.conclusion in FAILED else "other"

    def elapsed(self, now: datetime) -> float:
        """Seconds it has been running, or took once it finished."""
        end = now if self.state == "running" else self.updated_at

        return (end - self.started_at).total_seconds()

    @property
    def commit(self) -> tuple[str, str]:
        """What groups runs together: the repo and the commit they ran on."""
        return (self.repo, self.sha or str(self.id))

    @property
    def workflow_url(self) -> str | None:
        """The workflow's page, for one defined in the repo's own workflows.

        GitHub's built-in workflows, such as default CodeQL setup, report a
        ``dynamic/...`` path and have no page of their own.
        """
        folder, _, file = self.workflow_path.partition("@")[0].rpartition("/")

        if folder != ".github/workflows" or not file:
            return None

        return f"https://github.com/{self.repo}/actions/workflows/{file}"


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


def parse_run(repo: str, raw: dict) -> Run | None:
    """One run from the REST payload, or None when it lacks the essentials."""
    run_id = number_at(raw, "id")
    url = string_at(raw, "html_url")
    created = parse_date(raw.get("created_at"))

    if run_id is None or url is None or created is None:
        return None

    return Run(
        id=int(run_id),
        attempt=int(number_at(raw, "run_attempt") or 1),
        repo=repo,
        workflow=string_at(raw, "name") or "Workflow",
        sha=string_at(raw, "head_sha") or "",
        title=(string_at(object_at(raw, "head_commit"), "message") or "").split("\n")[0]
        or string_at(raw, "display_title")
        or "",
        number=int(number_at(raw, "run_number") or 0),
        branch=string_at(raw, "head_branch") or "",
        event=string_at(raw, "event") or "",
        actor=string_at(object_at(raw, "triggering_actor"), "login") or "",
        status=string_at(raw, "status") or "",
        conclusion=string_at(raw, "conclusion") or "",
        url=url,
        workflow_path=string_at(raw, "path") or "",
        created_at=created,
        started_at=parse_date(raw.get("run_started_at")) or created,
        updated_at=parse_date(raw.get("updated_at")) or created,
    )


def gh_api(gh: str, path: str, *flags: str) -> str:
    try:
        return run_command([gh, "api", path, *flags], timeout=15)
    except subprocess.TimeoutExpired:
        raise TimeoutError from None


def repo_runs(gh: str, repo: str, per_repo: int, actor: str | None) -> list[Run]:
    query = f"per_page={per_repo}&exclude_pull_requests=true"
    query += f"&actor={actor}" if actor else ""
    payload = json.loads(gh_api(gh, f"repos/{repo}/actions/runs?{query}"))
    runs = [parse_run(repo, raw) for raw in payload.get("workflow_runs") or []]

    return [run for run in runs if run is not None]


def latest(
    gh: str,
    repos: list[str],
    discover: int,
    exclude: list[str],
    limit: int,
    actor: str | None,
) -> Latest:
    """The ``limit`` newest runs across the watched repos, newest first."""
    try:
        # Asks for enough extra to still have ``discover`` after excluding.
        candidates = (
            repos
            or gh_api(
                gh,
                f"user/repos?sort=pushed&per_page={discover + len(exclude)}",
                "--jq",
                ".[].full_name",
            ).split()
        )
        watched = [repo for repo in candidates if repo not in exclude]
        watched = watched if repos else watched[:discover]

        if actor == "@me":
            actor = gh_api(gh, "user", "--jq", ".login").strip()
    except (RuntimeError, TimeoutError) as error:
        return Latest(errors=[clean_error(error)])

    def fetch(repo: str) -> list[Run] | str:
        try:
            return repo_runs(gh, repo, limit, actor)
        except (RuntimeError, TimeoutError, ValueError) as error:
            return f"{repo}: {clean_error(error)}"

    fetched = gather(watched, fetch)
    runs = [run for result in fetched if isinstance(result, list) for run in result]
    newest = sorted(runs, key=lambda run: run.created_at, reverse=True)[:limit]

    return Latest(newest, [result for result in fetched if isinstance(result, str)])


def grouped[K](runs: list[Run], key: Callable[[Run], K]) -> dict[K, list[Run]]:
    """Groups runs by ``key``, groups ordered by their newest run."""
    groups: dict[K, list[Run]] = {}

    for run in runs:
        groups.setdefault(key(run), []).append(run)

    return groups


def log_tail(log: str, count: int = LOG_LINES) -> list[str]:
    """The last lines before a job log's first error, as GitHub shows them.

    Collapsed groups (a step's command and env, setup output) are left out,
    as the web view folds them away too.
    """
    kept: list[str] = []
    folded = False

    for raw in log.splitlines():
        line = _ANSI_CODE.sub("", _TIMESTAMP.sub("", raw)).rstrip()

        if line.startswith("##[group]"):
            folded = True
        elif line.startswith("##[endgroup]"):
            folded = False
        elif line.startswith("##[error]"):
            kept.append(line.removeprefix("##[error]"))
            break
        elif line.strip() and not folded:
            kept.append(line)

    return kept[-count:]


def failed_jobs(gh: str, run: Run) -> list[FailedJob]:
    payload = json.loads(gh_api(gh, f"repos/{run.repo}/actions/runs/{run.id}/jobs"))
    jobs = [job for job in payload.get("jobs") or [] if isinstance(job, dict)]
    failed = [job for job in jobs if job.get("conclusion") in FAILED]

    return [
        FailedJob(
            name=string_at(job, "name") or "Job",
            step=next(
                (
                    string_at(step, "name") or ""
                    for step in job.get("steps") or []
                    if isinstance(step, dict) and step.get("conclusion") in FAILED
                ),
                "",
            ),
            url=string_at(job, "html_url") or run.url,
            log=log_tail(
                gh_api(gh, f"repos/{run.repo}/actions/jobs/{job.get('id')}/logs")
            ),
        )
        for job in failed[:MAX_FAILED_JOBS]
    ]


def diagnose(gh: str, runs: list[Run]) -> dict[int, Diagnosis]:
    """What each failed run's log said, read once per run attempt."""
    cached = state.load(PLUGIN, FAILURES_FILE)

    def read(run: Run) -> Diagnosis:
        try:
            return [FailedJob(**job) for job in cached[f"{run.id}/{run.attempt}"]]
        except (KeyError, TypeError):
            pass

        try:
            return failed_jobs(gh, run)
        except (RuntimeError, TimeoutError, ValueError) as error:
            return clean_error(error)

    diagnoses = dict(zip((run.id for run in runs), gather(runs, read), strict=True))
    state.save(
        PLUGIN,
        {
            f"{run.id}/{run.attempt}": [asdict(job) for job in diagnoses[run.id]]
            for run in runs
            if isinstance(diagnoses[run.id], list)
        },
        FAILURES_FILE,
    )

    return diagnoses


def overall(runs: list[Run]) -> str:
    """The state of a group of runs: the worst of each workflow's latest."""
    latest = grouped(runs, lambda run: run.workflow_path or run.workflow)
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


def Square(run: Run) -> str:
    return Indicator(COLORS[run.state], SQUARE)


def Squares(runs: list[Run]) -> Node:
    """The menu bar: a square per run, the runs of one commit side by side."""
    commits = grouped(runs, lambda run: run.commit).values()

    return Indicators(
        *(
            ["".join(Square(run) for run in commit) for commit in commits]
            or [Indicator(COLORS["other"], SQUARE)]
        )
    )


def Outcome(run: Run, now: datetime) -> str:
    took = duration(run.elapsed(now))

    match run.state:
        case "running":
            return f"{run.status.replace('_', ' ').capitalize()} for {took}"
        case "success":
            return f"Succeeded in {took}"
        case "failure":
            return f"Failed in {took}"
        case _:
            return f"{run.conclusion.replace('_', ' ').capitalize()} after {took}"


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


def WorkflowRun(run: Run, diagnosis: Diagnosis | None, gh: str, now: datetime) -> Node:
    """One run, with its details and links in a submenu."""
    when = (
        f"running {duration(run.elapsed(now))}"
        if run.state == "running"
        else f"{duration((now - run.updated_at).total_seconds())} ago"
    )

    return Item(
        elbow(f"{Square(run)} {escape_strict(run.workflow)} · {when}"),
        Item(f"#{run.number} · {run.event} by {run.actor}", font=MONOSPACE),
        Item(Outcome(run, now), font=MONOSPACE),
        Failure(diagnosis),
        Separator(),
        Link("Open run", run.url),
        Link("Open workflow", run.workflow_url) if run.workflow_url else None,
        Item(
            "Show failed log in Terminal",
            bash=gh,
            params=["run", "view", run.id, "--log-failed", "--repo", run.repo],
            terminal=True,
        )
        if run.state == "failure"
        else None,
        href=run.url,
        ansi=True,
        font=MONOSPACE,
        length=70,
    )


def Commit(
    runs: list[Run], diagnoses: dict[int, Diagnosis], gh: str, now: datetime
) -> Node:
    """A commit's heading, linking to it, over the runs it triggered."""
    head = runs[0]
    heading = " · ".join(
        part for part in (head.sha[:7], head.branch, head.title) if part
    )

    return [
        Item(
            f"{Indicator(COLORS[overall(runs)], SQUARE)} "
            + colorize(escape_strict(heading), "muted"),
            ansi=True,
            font=MONOSPACE,
            length=70,
            href=f"https://github.com/{head.repo}/commit/{head.sha}"
            if head.sha
            else None,
        ),
        [WorkflowRun(run, diagnoses.get(run.id), gh, now) for run in runs],
    ]


def Repo(
    repo: str,
    runs: list[Run],
    diagnoses: dict[int, Diagnosis],
    gh: str,
    now: datetime,
) -> Node:
    return [
        Item(repo, font=MONOSPACE, size=13, href=f"https://github.com/{repo}/actions"),
        [
            Commit(commit, diagnoses, gh, now)
            for commit in grouped(runs, lambda run: run.commit).values()
        ],
        Separator(),
    ]


def Problem(error: str) -> Node:
    return Item(
        colorize(f"⚠ {escape_strict(error)}", "critical"), ansi=True, font=MONOSPACE
    )


if __name__ == "__main__":
    settings = SETTINGS
    squares = int(number_at(settings, "squares") or 5)
    listed = int(number_at(settings, "listed") or 15)
    repos = strings_at(settings, "repos")
    discover = int(number_at(settings, "discover") or 10)
    exclude = strings_at(settings, "exclude")
    actor = string_at(settings, "actor")

    gh = which("gh")
    found = (
        latest(gh, repos, discover, exclude, max(squares, listed), actor)
        if gh
        else Latest(errors=["gh not found on PATH"])
    )
    shown = found.runs[:listed]
    diagnoses = diagnose(gh, [run for run in shown if run.state == "failure"])
    now = datetime.now(UTC)

    show(
        Squares(found.runs[:squares]),
        [
            Repo(repo, runs, diagnoses, gh, now)
            for repo, runs in grouped(shown, lambda run: run.repo).items()
        ]
        or Item("No workflow runs"),
        [Problem(error) for error in found.errors],
        Separator(),
        Refresh(),
    )
