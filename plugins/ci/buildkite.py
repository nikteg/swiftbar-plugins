"""Buildkite builds, through ``bk api``.

``bk`` keeps the token in the Keychain and prefixes every path with the
organisation it is logged in to, so nothing here handles either. Unlike
GitHub, one call lists the builds of every pipeline.
"""

from __future__ import annotations

import json
import re
import subprocess

from swiftbar_lib.data import number_at, object_at, string_at
from swiftbar_lib.dates import parse_date
from swiftbar_lib.errors import clean_error
from swiftbar_lib.shell import run as run_command

from .runs import ANSI_CODE, LOG_LINES, MAX_FAILED_JOBS, FailedJob, Latest, Run

#: Buildkite's build states, as the menu's four. ``failing`` is a build still
#: running with a job already failed; ``blocked`` has passed so far and waits
#: on a manual step. Anything else (canceled, skipped, not_run) is other.
STATES = {
    "creating": "running",
    "scheduled": "running",
    "running": "running",
    "failing": "failure",
    "failed": "failure",
    "passed": "success",
    "blocked": "success",
}
FAILED_JOBS = {"failed", "timed_out"}

#: A GitHub remote in either form: git@github.com:o/r.git, https://github.com/o/r
_GITHUB_REMOTE = re.compile(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?/?$")
#: The agent's per-line timestamp, an APC sequence: ESC _ bk;t=... BEL.
_TIMESTAMP = re.compile(r"\x1b_bk;t=\d+\x07")
#: A log group header: "--- Title", "+++ Title", "~~~ Title", or "^^^ +++".
_GROUP = re.compile(r"^(?:(?:---|\+\+\+|~~~) \S|\^\^\^ \+\+\+$)")


def bk_api(bk: str, path: str) -> str:
    """A REST call; ``path`` is relative to the logged-in organisation."""
    try:
        return run_command([bk, "api", path], timeout=15)
    except subprocess.TimeoutExpired:
        raise TimeoutError from None


def github_repo(remote: str) -> str | None:
    """``owner/name`` from a GitHub remote URL, or None for anywhere else."""
    match = _GITHUB_REMOTE.search(remote)

    return match.group(1) if match else None


def failed(jobs: object) -> list[dict]:
    """The jobs that failed the build; a soft failure does not."""
    return [
        job
        for job in (jobs if isinstance(jobs, list) else [])
        if isinstance(job, dict)
        and job.get("state") in FAILED_JOBS
        and not job.get("soft_failed")
    ]


def parse_build(raw: dict, bk: str) -> Run | None:
    """One build, or None when it lacks the essentials."""
    build_id = string_at(raw, "id")
    url = string_at(raw, "web_url")
    created = parse_date(raw.get("created_at"))
    pipeline = object_at(raw, "pipeline") or {}
    slug = string_at(pipeline, "slug")

    if build_id is None or url is None or created is None or slug is None:
        return None

    status = string_at(raw, "state") or ""
    repo = github_repo(string_at(pipeline, "repository") or "")
    sha = string_at(raw, "commit") or ""
    first_failed = next((string_at(job, "id") for job in failed(raw.get("jobs"))), None)

    return Run(
        id=build_id,
        attempt=1,
        repo=repo or slug,
        repo_url=f"https://github.com/{repo}" if repo else None,
        workflow=string_at(pipeline, "name") or slug,
        workflow_key=slug,
        workflow_url=string_at(pipeline, "web_url"),
        sha=sha,
        commit_url=f"https://github.com/{repo}/commit/{sha}" if repo and sha else None,
        title=(string_at(raw, "message") or "").split("\n")[0],
        number=int(number_at(raw, "number") or 0),
        branch=string_at(raw, "branch") or "",
        event=string_at(raw, "source") or "",
        actor=string_at(object_at(raw, "creator"), "name")
        or string_at(object_at(raw, "author"), "name")
        or "",
        state=STATES.get(status, "other"),
        status=status,
        url=url,
        created_at=created,
        started_at=parse_date(raw.get("started_at")) or created,
        finished_at=parse_date(raw.get("finished_at")),
        log_command=(bk, "job", "log", first_failed, "--no-timestamps")
        if first_failed
        else (),
    )


def builds(bk: str, repos: list[str], exclude: list[str], limit: int) -> Latest:
    """The ``limit`` newest builds in the organisation, newest first.

    ``repos`` and ``exclude`` match a build's GitHub ``owner/name``, or its
    pipeline slug for a pipeline that builds from somewhere else.
    """
    try:
        payload = json.loads(bk_api(bk, f"/builds?per_page={limit}"))
    except (RuntimeError, TimeoutError, ValueError) as error:
        return Latest(errors=[clean_error(error)])

    found = [
        parse_build(raw, bk)
        for raw in (payload if isinstance(payload, list) else [])
        if isinstance(raw, dict)
    ]

    return Latest(
        [
            run
            for run in found
            if run is not None
            and run.repo not in exclude
            and (not repos or run.repo in repos)
        ]
    )


def log_tail(log: str, count: int = LOG_LINES) -> list[str]:
    """The last lines of a job log, up to the agent's 🚨 error line.

    Group headers (``--- Title`` and the like) are left out; the agent draws
    them as folds rather than as output.
    """
    kept: list[str] = []

    for raw in log.replace("\r", "").split("\n"):
        line = ANSI_CODE.sub("", _TIMESTAMP.sub("", raw)).rstrip()

        if _GROUP.match(line):
            continue

        if line.strip():
            kept.append(line)

        if line.startswith("🚨 Error"):
            break

    return kept[-count:]


def failed_jobs(bk: str, run: Run) -> list[FailedJob]:
    """Each failed job's name, exit status and log tail."""
    build = f"/pipelines/{run.workflow_key}/builds/{run.number}"
    payload = json.loads(bk_api(bk, build))

    def log(job: dict) -> list[str]:
        body = json.loads(bk_api(bk, f"{build}/jobs/{job.get('id')}/log"))

        return log_tail(string_at(body, "content") or "")

    return [
        FailedJob(
            name=string_at(job, "name") or string_at(job, "label") or "Job",
            step=f"exit {job['exit_status']}"
            if isinstance(job.get("exit_status"), int)
            else "",
            url=string_at(job, "web_url") or run.url,
            log=log(job),
        )
        for job in failed(payload.get("jobs"))[:MAX_FAILED_JOBS]
    ]
