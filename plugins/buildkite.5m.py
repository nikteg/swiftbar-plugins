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
    Menu bar: the newest few commits, newest first, a squircle for each build
    on one, a thin line between commits — orange while it is scheduled or
    running, green when it passed, red when it failed or is failing, grey
    when it was canceled or skipped. A build blocked on a manual step after
    passing so far counts as passed.
    Dropdown: the same groups in the same order, then more under "Not in menu
    bar": one per commit, newest first, a separator where the bar has its
    line, each commit headed by a squircle, the worst of each pipeline's
    latest build on it, its repo's name, short hash, branch and message; its
    submenu has the full hash, author and the whole message. Each build's row
    has its pipeline and build number; its submenu has the trigger and
    duration, and links to the build and its pipeline. A failed build also
    names each failed job and its exit status, shows the last lines of its log
    before the agent's error line, and offers to open the first failed job's
    full log in Terminal.

Configure
    In ~/.config/swiftbar-plugins/buildkite.json, outside the repo. Every key
    is optional; the defaults are at the bottom of this file.
      squares   How many commits get squares in the menu bar, one per build
                on each. Default 3.
      listed    How many commits the dropdown lists, each with all its
                builds. Default 10.
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
from ci.menu import Commits, Problem, Squares, View
from ci.runs import (
    DEFAULT_COLORS,
    Latest,
    diagnose,
    first_commits,
    newest,
)
from swiftbar_lib import config
from swiftbar_lib.ansi import palette
from swiftbar_lib.data import number_at, object_at, strings_at
from swiftbar_lib.output import show
from swiftbar_lib.shell import which
from swiftbar_lib.ui import Item, Refresh, Separator

PLUGIN = "buildkite"

#: This plugin's settings from outside the repo; see Configure above.
SETTINGS = config.load(__file__)

#: The colour of each state's squircle, overridable by ``colors`` in SETTINGS.
COLORS = palette(DEFAULT_COLORS, object_at(SETTINGS, "colors"))


if __name__ == "__main__":
    squares = int(number_at(SETTINGS, "squares") or 3)
    listed = int(number_at(SETTINGS, "listed") or 10)
    repos = strings_at(SETTINGS, "repos")
    exclude = strings_at(SETTINGS, "exclude")

    bk = which("bk")
    found = (
        # A commit can have a build per pipeline, so ask for enough of them
        # to fill every group; Buildkite pages at 100.
        buildkite.builds(bk, repos, exclude, min(100, 3 * max(squares, listed)))
        if bk
        else Latest(errors=["bk not found on PATH"])
    )
    recent = newest(found.runs)
    shown = first_commits(recent, listed)
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
        Squares(recent, COLORS, squares),
        Commits(shown, view, squares) or Item("No builds"),
        [Problem(error) for error in found.errors],
        Separator(),
        Refresh(),
    )
