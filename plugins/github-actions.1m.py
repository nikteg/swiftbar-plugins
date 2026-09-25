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
    Menu bar: the newest few commits, newest first, a squircle for each run
    on one, a thin line between commits — orange while it is queued or running, green
    when it succeeded, red when it failed, grey when it was cancelled or
    skipped.
    Dropdown: the same groups in the same order, then the rest in a "more
    commits" submenu: one per commit, newest first across repos, a separator
    where the bar has its line. Each commit is headed by a squircle, the worst
    of each workflow's latest run on it, its repo's name, short hash, branch
    and message's first line; its submenu has the full hash, author, commit
    time, the whole message, and a row copying the hash. Each run's row has
    its workflow and run number; its submenu has the trigger and duration, and
    links to the run and to its workflow's page. A failed run also names each
    failed job and step, shows the last lines of its log before the error, and
    offers to open the full failed log in Terminal.

Configure
    In ~/.config/swiftbar-plugins/github-actions.json, outside the repo, so
    which repos you watch is never committed. Every key is optional; the
    defaults are at the bottom of this file.
      squares   How many commits get squares in the menu bar, one per run
                on each. Default 3.
      listed    How many commits the dropdown lists, each with all its
                runs. Default 10.
      repos     ``owner/name`` repos to watch. Empty means the ``discover``
                most recently pushed repos you have access to.
      discover  How many repos to look in when ``repos`` is empty. Default 10.
      exclude   ``owner/name`` repos never to show. Discovery skips past
                them, so it still finds ``discover`` others.
      actor     A login, or ``@me``, to show only runs that person triggered.
      colors    A colour per state — running, success, failure, other — as
                "#rrggbb", a 256-colour number, or a name such as "warning".
                Unset ones keep the defaults, GitHub's own softer shades; the
                squircles are images, so any colour draws exactly.

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

Implementation
    ci/ holds what this and the buildkite plugin share: the run model, the
    failure cache, and every menu component. Only the settings and the menu
    are here.

Requires
    ``gh``, logged in. A missing one is reported in the dropdown.

Refresh
    Every minute, from the ``1m`` in this file's name. Rename to change it.
"""

from datetime import UTC, datetime

from ci import github
from ci.menu import Commits, Problem, Squares, View
from ci.runs import DEFAULT_COLORS, Latest, diagnose, first_commits
from swiftbar_lib import config
from swiftbar_lib.ansi import palette
from swiftbar_lib.data import number_at, object_at, string_at, strings_at
from swiftbar_lib.output import show
from swiftbar_lib.shell import which
from swiftbar_lib.ui import Item, Refresh, Separator

PLUGIN = "github-actions"

#: This plugin's settings from outside the repo; see Configure above.
SETTINGS = config.load(__file__)

#: The colour of each state's squircle, overridable by ``colors`` in SETTINGS.
COLORS = palette(DEFAULT_COLORS, object_at(SETTINGS, "colors"))


if __name__ == "__main__":
    squares = int(number_at(SETTINGS, "squares") or 3)
    listed = int(number_at(SETTINGS, "listed") or 10)
    repos = strings_at(SETTINGS, "repos")
    discover = int(number_at(SETTINGS, "discover") or 10)
    exclude = strings_at(SETTINGS, "exclude")
    actor = string_at(SETTINGS, "actor")

    gh = which("gh")
    found = (
        github.latest(gh, repos, discover, exclude, max(squares, listed), actor)
        if gh
        else Latest(errors=["gh not found on PATH"])
    )
    shown = first_commits(found.runs, listed)
    view = View(
        now=datetime.now(UTC),
        colors=COLORS,
        diagnoses=diagnose(
            PLUGIN,
            [run for run in shown if run.state == "failure"],
            lambda run: github.failed_jobs(gh, run),
        ),
    )

    show(
        Squares(found.runs, COLORS, squares),
        Commits(shown, view, squares) or Item("No workflow runs"),
        [Problem(error) for error in found.errors],
        Separator(),
        Refresh(),
    )
