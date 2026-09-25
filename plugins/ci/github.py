"""GitHub Actions runs, through ``gh api``.

GitHub has no endpoint that lists runs across repos, so ``latest`` finds the
repos first and then fetches each one's runs in parallel.
"""

from __future__ import annotations

import json
import re
import subprocess

from swiftbar_lib.data import number_at, object_at, string_at
from swiftbar_lib.dates import parse_date
from swiftbar_lib.errors import clean_error
from swiftbar_lib.http import gather
from swiftbar_lib.shell import run as run_command

from .runs import ANSI_CODE, LOG_LINES, MAX_FAILED_JOBS, FailedJob, Latest, Run, newest

#: Every status GitHub reports for a run that has not finished.
ACTIVE = {"queued", "in_progress", "waiting", "requested", "pending"}
FAILED = {"failure", "timed_out", "startup_failure"}

_TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ?")


def gh_api(gh: str, path: str, *flags: str) -> str:
    try:
        return run_command([gh, "api", path, *flags], timeout=15)
    except subprocess.TimeoutExpired:
        raise TimeoutError from None


def workflow_page(repo: str, path: str) -> str | None:
    """A workflow's page, for one defined in the repo's own workflows.

    GitHub's built-in workflows, such as default CodeQL setup, report a
    ``dynamic/...`` path and have no page of their own.
    """
    folder, _, file = path.partition("@")[0].rpartition("/")

    if folder != ".github/workflows" or not file:
        return None

    return f"https://github.com/{repo}/actions/workflows/{file}"


def state_of(status: str, conclusion: str) -> str:
    if status in ACTIVE:
        return "running"

    if conclusion == "success":
        return "success"

    return "failure" if conclusion in FAILED else "other"


def parse_run(repo: str, raw: dict, gh: str) -> Run | None:
    """One run from the REST payload, or None when it lacks the essentials."""
    run_id = number_at(raw, "id")
    url = string_at(raw, "html_url")
    created = parse_date(raw.get("created_at"))

    if run_id is None or url is None or created is None:
        return None

    status = string_at(raw, "status") or ""
    conclusion = string_at(raw, "conclusion") or ""
    state = state_of(status, conclusion)
    path = string_at(raw, "path") or ""
    sha = string_at(raw, "head_sha") or ""
    message = string_at(object_at(raw, "head_commit"), "message") or ""

    return Run(
        id=str(int(run_id)),
        attempt=int(number_at(raw, "run_attempt") or 1),
        repo=repo,
        workflow=string_at(raw, "name") or "Workflow",
        workflow_key=path or string_at(raw, "name") or "",
        workflow_url=workflow_page(repo, path),
        sha=sha,
        commit_url=f"https://github.com/{repo}/commit/{sha}" if sha else None,
        title=message.split("\n")[0] or string_at(raw, "display_title") or "",
        message=message or string_at(raw, "display_title") or "",
        author=string_at(object_at(object_at(raw, "head_commit"), "author"), "name")
        or "",
        committed_at=parse_date((object_at(raw, "head_commit") or {}).get("timestamp")),
        number=int(number_at(raw, "run_number") or 0),
        branch=string_at(raw, "head_branch") or "",
        event=string_at(raw, "event") or "",
        actor=string_at(object_at(raw, "triggering_actor"), "login") or "",
        state=state,
        status=status if state == "running" else conclusion or status,
        url=url,
        created_at=created,
        started_at=parse_date(raw.get("run_started_at")) or created,
        finished_at=None
        if status in ACTIVE
        else parse_date(raw.get("updated_at")) or created,
        log_command=(gh, "run", "view", str(int(run_id)), "--log-failed")
        + ("--repo", repo),
    )


def repo_runs(gh: str, repo: str, per_repo: int, actor: str | None) -> list[Run]:
    query = f"per_page={per_repo}&exclude_pull_requests=true"
    query += f"&actor={actor}" if actor else ""
    payload = json.loads(gh_api(gh, f"repos/{repo}/actions/runs?{query}"))
    runs = [parse_run(repo, raw, gh) for raw in payload.get("workflow_runs") or []]

    return [run for run in runs if run is not None]


def latest(
    gh: str,
    repos: list[str],
    discover: int,
    exclude: list[str],
    limit: int,
    actor: str | None,
) -> Latest:
    """The latest ``limit`` runs of each watched repo, newest first overall.

    Not cut to ``limit`` in total: the menu counts commits, and a cut here
    could split one.
    """
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

    return Latest(
        newest(runs), [result for result in fetched if isinstance(result, str)]
    )


def log_tail(log: str, count: int = LOG_LINES) -> list[str]:
    """The last lines before a job log's first error, as GitHub shows them.

    Collapsed groups (a step's command and env, setup output) are left out,
    as the web view folds them away too.
    """
    kept: list[str] = []
    folded = False

    for raw in log.splitlines():
        line = ANSI_CODE.sub("", _TIMESTAMP.sub("", raw)).rstrip()

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
    """Each failed job's name, failed step and log tail.

    Read from the log rather than from check-run annotations, which a
    fine-grained token often cannot read.
    """
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
