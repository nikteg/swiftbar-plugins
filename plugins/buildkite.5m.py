#!/usr/bin/env -S /opt/homebrew/bin/uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
# <swiftbar.title>Buildkite</swiftbar.title>
# <swiftbar.author>nikteg</swiftbar.author>
# <swiftbar.author.github>nikteg</swiftbar.author.github>
# <swiftbar.desc>The latest Buildkite builds in your organisation</swiftbar.desc>
# <swiftbar.dependencies>uv,bk</swiftbar.dependencies>
"""The latest Buildkite builds in your organisation.

Shows
    The same menu as github-actions, for Buildkite builds.
    Menu bar: one square per build for the newest few, newest first, the
    builds of one commit side by side — orange while it is scheduled or
    running, green when it passed, red when it failed or is failing, grey
    when it was canceled or skipped. A build blocked on a manual step after
    passing so far counts as passed.
    Dropdown: more of the latest builds, grouped by repo and then by commit,
    each commit headed by a square, the worst of each pipeline's latest build
    on it. Each build's submenu has the trigger and duration, and links to the
    build and its pipeline. A failed build also names each failed job and its
    exit status, shows the last lines of its log before the agent's error
    line, and offers to open the first failed job's full log in Terminal.

Configure
    In ~/.config/swiftbar-plugins/buildkite.json, outside the repo. Every key
    is optional; the defaults are at the bottom of this file.
      squares   How many builds get a square in the menu bar. Default 5.
      listed    How many builds the dropdown lists. Default 15.
      repos     Only these. A pipeline building a GitHub repo is matched by
                its ``owner/name``, any other by its pipeline slug.
      exclude   Never these, matched the same way.
      colors    A colour per state — running, success, failure, other — as
                in github-actions.

    {"exclude": ["acme/legacy-app"], "colors": {"running": "#ff9500"}}

Source
    ``bk api``, in the organisation ``bk`` is logged in to, with the token
    ``bk auth login`` keeps in the Keychain. One call lists the builds of
    every pipeline. A failed build costs one call for its jobs and one per
    failed job's log, once: what was read is kept in failures.json in the
    plugin's cache directory.

Requires
    ``bk``, logged in: ``bk auth login --scopes read_only`` is enough. A
    missing one is reported in the dropdown.

Refresh
    Every five minutes, from the ``5m`` in this file's name. Rename to change
    it.
"""

from datetime import UTC, datetime

from ci import buildkite
from ci.menu import Problem, Repo, Squares, View
from ci.runs import DEFAULT_COLORS, Latest, diagnose, grouped, newest
from swiftbar_lib import config
from swiftbar_lib.ansi import palette
from swiftbar_lib.data import number_at, object_at, strings_at
from swiftbar_lib.output import show
from swiftbar_lib.shell import which
from swiftbar_lib.ui import Item, Refresh, Separator

PLUGIN = "buildkite"

#: This plugin's settings from outside the repo; see Configure above.
SETTINGS = config.load(__file__)

#: The colour of each state's square, overridable by ``colors`` in SETTINGS.
COLORS = palette(DEFAULT_COLORS, object_at(SETTINGS, "colors"))


if __name__ == "__main__":
    squares = int(number_at(SETTINGS, "squares") or 5)
    listed = int(number_at(SETTINGS, "listed") or 15)
    repos = strings_at(SETTINGS, "repos")
    exclude = strings_at(SETTINGS, "exclude")

    bk = which("bk")
    found = (
        buildkite.builds(bk, repos, exclude, max(squares, listed))
        if bk
        else Latest(errors=["bk not found on PATH"])
    )
    recent = newest(found.runs, max(squares, listed))
    shown = recent[:listed]
    view = View(
        now=datetime.now(UTC),
        colors=COLORS,
        nouns=("build", "pipeline"),
        diagnoses=diagnose(
            PLUGIN,
            [run for run in shown if run.state == "failure"],
            lambda run: buildkite.failed_jobs(bk, run),
        ),
    )

    show(
        Squares(recent[:squares], COLORS),
        [
            Repo(repo, runs, view)
            for repo, runs in grouped(shown, lambda r: r.repo).items()
        ]
        or Item("No builds"),
        [Problem(error) for error in found.errors],
        Separator(),
        Refresh(),
    )
