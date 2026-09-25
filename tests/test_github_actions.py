import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from unittest import mock

from ci import github
from ci.menu import Commits, Squares, View, WorkflowRun, message_lines
from ci.runs import (
    DEFAULT_COLORS,
    FailedJob,
    diagnose,
    duration,
    first_commits,
    overall,
)
from plugin_loader import load
from png_fixture import rows, squares
from swiftbar_lib import config
from swiftbar_lib import state as state_files
from swiftbar_lib.output import render

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
GH = "/opt/homebrew/bin/gh"
VIEW = View(NOW, DEFAULT_COLORS)

#: The default squircle colours, as the images' pixels come back.
GREEN, ORANGE, RED, GREY = (63, 185, 80), (210, 153, 34), (248, 81, 73), (139, 148, 158)


def read(run):
    return github.failed_jobs(GH, run)


def raw(run_id, created, status="completed", conclusion="success", **extra):
    return {
        "id": run_id,
        "html_url": f"https://github.com/o/r/actions/runs/{run_id}",
        "name": "CI",
        "display_title": "Fix the thing",
        "head_sha": f"sha{run_id}",
        "head_commit": {
            "message": "Fix the thing\n\nWith a body.",
            "author": {"name": "Octo Cat"},
            "timestamp": "2026-09-25T11:40:00Z",
        },
        "run_number": run_id,
        "head_branch": "main",
        "event": "push",
        "triggering_actor": {"login": "me"},
        "status": status,
        "conclusion": conclusion,
        "created_at": created,
        "run_started_at": created,
        "updated_at": "2026-09-25T11:55:00Z",
        "path": ".github/workflows/ci.yml",
        **extra,
    }


def run(repo="o/r", **fields):
    return github.parse_run(repo, raw(**fields), GH)


class ParseRunTest(unittest.TestCase):
    def test_maps_status_and_conclusion_to_a_state(self):
        cases = [
            ("in_progress", None, "running"),
            ("queued", None, "running"),
            ("completed", "success", "success"),
            ("completed", "failure", "failure"),
            ("completed", "timed_out", "failure"),
            ("completed", "cancelled", "other"),
        ]

        for status, conclusion, state in cases:
            with self.subTest(status=status, conclusion=conclusion):
                parsed = run(
                    run_id=1,
                    created="2026-09-25T11:50:00Z",
                    status=status,
                    conclusion=conclusion,
                )
                self.assertEqual(parsed.state, state)

    def test_skips_a_run_without_an_id_or_url(self):
        self.assertIsNone(github.parse_run("o/r", {"name": "CI"}, GH))

    def test_links_a_repo_workflow_to_its_page(self):
        parsed = run(run_id=1, created="2026-09-25T11:50:00Z")

        self.assertEqual(
            parsed.workflow_url, "https://github.com/o/r/actions/workflows/ci.yml"
        )

    def test_has_no_workflow_page_for_a_dynamic_workflow(self):
        parsed = run(
            run_id=1,
            created="2026-09-25T11:50:00Z",
            path="dynamic/github-code-scanning/codeql",
        )

        self.assertIsNone(parsed.workflow_url)

    def test_measures_a_running_run_up_to_now(self):
        parsed = run(run_id=1, created="2026-09-25T11:50:00Z", status="in_progress")

        self.assertEqual(parsed.elapsed(NOW), 600)


class LatestTest(unittest.TestCase):
    def fake_gh(self, responses):
        def gh_api(gh, path, *flags):
            answer = responses[path.partition("?")[0]]

            if isinstance(answer, Exception):
                raise answer

            return answer

        return mock.patch.object(github, "gh_api", gh_api)

    def test_keeps_the_newest_runs_across_repos(self):
        responses = {
            "user/repos": "o/a\no/b\n",
            "repos/o/a/actions/runs": json.dumps(
                {
                    "workflow_runs": [
                        raw(1, "2026-09-25T11:00:00Z"),
                        raw(2, "2026-09-25T09:00:00Z"),
                    ]
                }
            ),
            "repos/o/b/actions/runs": json.dumps(
                {"workflow_runs": [raw(3, "2026-09-25T10:00:00Z")]}
            ),
        }

        with self.fake_gh(responses):
            found = github.latest(GH, [], discover=10, exclude=[], limit=2, actor=None)

        self.assertEqual(
            [(r.repo, r.id) for r in found.runs],
            [("o/a", "1"), ("o/b", "3"), ("o/a", "2")],
        )
        self.assertEqual(found.errors, [])

    def test_skips_excluded_repos_and_still_discovers_enough(self):
        requested = []
        empty = json.dumps({"workflow_runs": []})

        def gh_api(gh, path, *flags):
            requested.append(path)

            return "o/a\no/skip\no/b\n" if path.startswith("user/repos") else empty

        with mock.patch.object(github, "gh_api", gh_api):
            github.latest(GH, [], discover=2, exclude=["o/skip"], limit=5, actor=None)

        self.assertEqual(requested[0], "user/repos?sort=pushed&per_page=3")
        self.assertEqual(
            sorted(requested[1:]),
            [
                "repos/o/a/actions/runs?per_page=5&exclude_pull_requests=true",
                "repos/o/b/actions/runs?per_page=5&exclude_pull_requests=true",
            ],
        )

    def test_reports_a_failing_repo_without_losing_the_others(self):
        responses = {
            "repos/o/a/actions/runs": json.dumps(
                {"workflow_runs": [raw(1, "2026-09-25T11:00:00Z")]}
            ),
            "repos/o/b/actions/runs": RuntimeError("gh: Not Found (HTTP 404)"),
        }

        with self.fake_gh(responses):
            found = github.latest(
                GH, ["o/a", "o/b"], discover=10, exclude=[], limit=5, actor=None
            )

        self.assertEqual([r.id for r in found.runs], ["1"])
        self.assertEqual(found.errors, ["o/b: gh: Not Found (HTTP 404)"])

    def test_reports_a_failed_discovery_as_the_only_error(self):
        with self.fake_gh({"user/repos": RuntimeError("not logged in")}):
            found = github.latest(GH, [], discover=10, exclude=[], limit=5, actor=None)

        self.assertEqual((found.runs, found.errors), ([], ["not logged in"]))


class RenderTest(unittest.TestCase):
    def test_draws_a_square_per_run_with_a_commits_runs_side_by_side(self):
        runs = [
            run(run_id=1, created="2026-09-25T11:50:00Z", status="in_progress"),
            run(run_id=2, created="2026-09-25T11:45:00Z", head_sha="sha1"),
            run(run_id=3, created="2026-09-25T11:40:00Z", conclusion="failure"),
        ]
        title = Squares(runs, DEFAULT_COLORS, 5)

        self.assertEqual(
            squares(title.attrs["image"]),
            [[ORANGE, GREEN], [RED]],
        )
        self.assertEqual(render(title).split(" | ")[0], "")

    def test_counts_commits_not_runs_and_never_cuts_one_short(self):
        runs = [
            run(run_id=1, created="2026-09-25T11:50:00Z", head_sha="a"),
            run(run_id=2, created="2026-09-25T11:49:00Z", head_sha="a"),
            run(run_id=3, created="2026-09-25T11:48:00Z", head_sha="b"),
            run(run_id=4, created="2026-09-25T11:47:00Z", head_sha="b"),
            run(run_id=5, created="2026-09-25T11:46:00Z", head_sha="c"),
        ]
        title = Squares(runs, DEFAULT_COLORS, 2)

        self.assertEqual(
            squares(title.attrs["image"]), [[GREEN, GREEN], [GREEN, GREEN]]
        )

    def test_lists_a_number_of_whole_commits(self):
        runs = [
            run(run_id=1, created="2026-09-25T11:50:00Z", head_sha="a"),
            run(run_id=2, created="2026-09-25T11:49:00Z", head_sha="b"),
            run(run_id=3, created="2026-09-25T11:48:00Z", head_sha="b"),
            run(run_id=4, created="2026-09-25T11:47:00Z", head_sha="c"),
        ]

        self.assertEqual([r.id for r in first_commits(runs, 2)], ["1", "2", "3"])

    def test_draws_a_grey_square_when_there_are_no_runs(self):
        self.assertEqual(
            squares(Squares([], DEFAULT_COLORS, 5).attrs["image"]), [[GREY]]
        )

    def test_heads_each_commit_with_its_repo_over_its_runs(self):
        runs = [
            run(run_id=1, created="2026-09-25T11:50:00Z", head_sha="abcdef123456"),
            run(run_id=2, created="2026-09-25T11:45:00Z", head_sha="abcdef123456"),
            run(run_id=3, created="2026-09-25T11:40:00Z"),
        ]
        output = render(Commits(runs, VIEW, 5))

        self.assertEqual(
            rows(output),
            [
                ("r \x1b[90m· abcdef1 · main · Fix the thing\x1b[0m", [GREEN], False),
                ("CI \x1b[90m#1 · 5m ago\x1b[0m", [GREEN], False),
                ("CI \x1b[90m#2 · 5m ago\x1b[0m", [GREEN], False),
                ("r \x1b[90m· sha3 · main · Fix the thing\x1b[0m", [GREEN], False),
                ("CI \x1b[90m#3 · 5m ago\x1b[0m", [GREEN], False),
            ],
        )
        self.assertIn(
            "\n--abcdef123456 | font=Menlo\n"
            "--main · Octo Cat | font=Menlo\n"
            "--Committed 20m ago · Fri 25 Sep "
            + datetime(2026, 9, 25, 11, 40, tzinfo=UTC).astimezone().strftime("%H:%M")
            + " | font=Menlo\n"
            "-----\n"
            "--Fix the thing | font=Menlo\n"
            "-----\n"
            "--With a body. | font=Menlo\n"
            "-----\n"
            "--Open commit | href=https://github.com/o/r/commit/abcdef123456\n"
            '--Copy hash | bash=/usr/bin/osascript param1=-e param2="set the clipboard'
            ' to \\"abcdef123456\\"" terminal=false refresh=false\n',
            output,
        )

    def test_wraps_a_message_for_a_menu_that_does_not(self):
        message = "Title\n\n\n" + "word " * 30 + "\n- a bullet\n-- flag\n"
        lines = message_lines(message)

        self.assertEqual(lines[:2], ["Title", None])
        self.assertTrue(all(len(line) <= 80 for line in lines if line))
        self.assertEqual(lines[-2:], ["• a bullet", "\u2010- flag"])

    def test_lists_commits_in_the_menu_bars_order_across_repos(self):
        runs = [
            run(repo="o/a", run_id=1, created="2026-09-25T11:50:00Z"),
            run(repo="o/b", run_id=2, created="2026-09-25T11:40:00Z"),
            run(repo="o/a", run_id=3, created="2026-09-25T11:30:00Z"),
        ]
        headings = [
            label.split(" ")[0]
            for label, _, _ in rows(render(Commits(runs, VIEW, 5)))
            if "\x1b[90m·" in label  # a commit heading, grey from its hash on
        ]
        bar = squares(Squares(runs, DEFAULT_COLORS, 5).attrs["image"])

        self.assertEqual(headings, ["a", "b", "a"])
        self.assertEqual(len(bar), len(headings))

    def test_heads_the_commits_the_menu_bar_leaves_out(self):
        runs = [
            run(run_id=1, created="2026-09-25T11:50:00Z", head_sha="x"),
            run(run_id=2, created="2026-09-25T11:40:00Z", head_sha="y"),
            run(run_id=3, created="2026-09-25T11:30:00Z", head_sha="z"),
        ]
        body = render(Commits(runs, VIEW, 2)).partition("---\n")[2].split("\n")
        marker = body.index(
            "\x1b[90mNot in menu bar\x1b[0m | ansi=true font=Menlo size=11"
        )

        self.assertEqual(body[marker - 1], "---")  # after the bar's last commit
        self.assertEqual(body[marker + 1], "---")  # and a line of its own under it
        self.assertTrue(body[marker + 2].startswith("r \x1b[90m· z · main"))
        self.assertNotIn("Not in menu bar", render(Commits(runs, VIEW, 3)))

    def test_separates_commits_like_the_menu_bar(self):
        runs = [
            run(run_id=1, created="2026-09-25T11:50:00Z", head_sha="x"),
            run(run_id=2, created="2026-09-25T11:40:00Z", head_sha="y"),
        ]
        body = render(Commits(runs, VIEW, 5)).partition("---\n")[2].split("\n")
        tops = [line for line in body if not line.startswith("--") or line == "---"]

        self.assertEqual(
            [line == "---" for line in tops],
            [False, False, True, False, False],
        )

    def test_colours_a_commit_by_each_workflows_latest_run(self):
        def at(minute, **fields):
            return run(created=f"2026-09-25T11:{minute}:00Z", **fields)

        scan = {"path": ".github/workflows/scan.yml"}
        cases = [
            (
                "fixed by a later run",
                [at(50, run_id=2), at(40, run_id=1, conclusion="failure")],
                "success",
            ),
            (
                "another workflow failed",
                [at(50, run_id=2), at(40, run_id=1, conclusion="failure", **scan)],
                "failure",
            ),
            (
                "failure beats running",
                [
                    at(50, run_id=2, status="in_progress"),
                    at(40, run_id=1, conclusion="failure", **scan),
                ],
                "failure",
            ),
            (
                "still running",
                [at(50, run_id=2, status="in_progress"), at(40, run_id=1, **scan)],
                "running",
            ),
            ("only cancelled", [at(50, run_id=2, conclusion="cancelled")], "other"),
        ]

        for name, runs, state in cases:
            with self.subTest(name):
                self.assertEqual(overall(runs), state)

    def test_details_a_run_in_its_submenu(self):
        running = run(run_id=7, created="2026-09-25T11:57:00Z", status="in_progress")
        output = render(WorkflowRun(running, VIEW))

        self.assertEqual(
            rows(output), [("CI \x1b[90m#7 · running 3m\x1b[0m", [ORANGE], False)]
        )
        self.assertIn(
            "ansi=true href=https://github.com/o/r/actions/runs/7 image=", output
        )
        self.assertIn(
            "--push by me | font=Menlo\n--In progress for 3m | font=Menlo", output
        )
        self.assertIn(
            "--Open run | href=https://github.com/o/r/actions/runs/7\n"
            "--Open workflow | href=https://github.com/o/r/actions/workflows/ci.yml",
            output,
        )
        self.assertNotIn("Terminal", output)


LOG = """\
2026-09-25T10:03:52.9566610Z ##[group]Run npm test
2026-09-25T10:03:52.9567061Z \x1b[36;1mnpm test\x1b[0m
2026-09-25T10:03:52.9646404Z ##[endgroup]
2026-09-25T10:04:12.5683630Z \x1b[31m✖ 1 test failed\x1b[0m
2026-09-25T10:04:12.5702980Z expected 2 to equal 3
2026-09-25T10:04:12.5703791Z 
2026-09-25T10:04:12.5757615Z ##[error]Process completed with exit code 1.
2026-09-25T10:04:12.5873348Z Post job cleanup.
"""


class DiagnoseTest(unittest.TestCase):
    def setUp(self):
        cache = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        patch = mock.patch.dict(os.environ, {"SWIFTBAR_PLUGIN_CACHE_PATH": cache.name})
        patch.start()
        self.addCleanup(patch.stop)

    def test_keeps_the_output_before_the_error_without_folded_groups(self):
        self.assertEqual(
            github.log_tail(LOG),
            [
                "✖ 1 test failed",
                "expected 2 to equal 3",
                "Process completed with exit code 1.",
            ],
        )

    def test_keeps_only_the_last_lines(self):
        self.assertEqual(
            github.log_tail(LOG, count=1), ["Process completed with exit code 1."]
        )

    def test_reads_each_failed_job_once_per_attempt(self):
        failed = run(run_id=9, created="2026-09-25T11:50:00Z", conclusion="failure")
        calls = []
        jobs = {
            "jobs": [
                {"id": 1, "name": "build", "conclusion": "success", "steps": []},
                {
                    "id": 2,
                    "name": "test",
                    "conclusion": "failure",
                    "html_url": "https://github.com/o/r/actions/runs/9/job/2",
                    "steps": [
                        {"name": "Checkout", "conclusion": "success"},
                        {"name": "Run tests", "conclusion": "failure"},
                    ],
                },
            ]
        }

        def gh_api(gh, path, *flags):
            calls.append(path)

            return json.dumps(jobs) if path.endswith("/jobs") else LOG

        with mock.patch.object(github, "gh_api", gh_api):
            first = diagnose("github-actions", [failed], read)
            second = diagnose("github-actions", [failed], read)

        self.assertEqual(
            calls, ["repos/o/r/actions/runs/9/jobs", "repos/o/r/actions/jobs/2/logs"]
        )
        self.assertEqual(first, second)
        (job,) = first["9"]
        self.assertEqual((job.name, job.step), ("test", "Run tests"))
        self.assertEqual(job.log[-1], "Process completed with exit code 1.")

    def test_reports_an_unreadable_log_and_tries_again_next_time(self):
        failed = run(run_id=9, created="2026-09-25T11:50:00Z", conclusion="failure")

        def gh_api(gh, path, *flags):
            raise RuntimeError("gh: Gone (HTTP 410)")

        with mock.patch.object(github, "gh_api", gh_api):
            self.assertEqual(
                diagnose("github-actions", [failed], read),
                {"9": "gh: Gone (HTTP 410)"},
            )

        self.assertEqual(state_files.load("github-actions", "failures.json"), {})

    def test_renders_the_failed_step_over_its_log(self):
        failed = run(run_id=9, created="2026-09-25T11:50:00Z", conclusion="failure")
        job = FailedJob(
            name="test",
            step="Run tests",
            url="https://github.com/o/r/actions/runs/9/job/2",
            log=["--- FAIL: TestThing", "exit code 1"],
        )
        output = render(WorkflowRun(failed, View(NOW, DEFAULT_COLORS, {"9": [job]})))

        self.assertIn(
            "--\x1b[31m✗ test › Run tests\x1b[0m | ansi=true font=Menlo "
            "href=https://github.com/o/r/actions/runs/9/job/2\n"
            "--│ --- FAIL: TestThing | font=Menlo size=11 length=100\n",
            output,
        )
        self.assertIn(
            "--Show failed log in Terminal | bash=/opt/homebrew/bin/gh param1=run "
            "param2=view param3=9 param4=--log-failed param5=--repo param6=o/r "
            "terminal=true",
            output,
        )


class ColorsTest(unittest.TestCase):
    def test_takes_square_colours_from_the_config_file(self):
        path = config.config_path("github-actions")
        path.write_text('{"colors": {"running": "#ff8700", "failure": "nope"}}')
        self.addCleanup(path.unlink)

        configured = load("github-actions.1m.py")
        running = run(run_id=1, created="2026-09-25T11:50:00Z", status="in_progress")

        output = render(WorkflowRun(running, View(NOW, configured.COLORS)))

        self.assertEqual(rows(output)[0][1], [(255, 135, 0)])
        self.assertEqual(configured.COLORS["failure"], DEFAULT_COLORS["failure"])


class DurationTest(unittest.TestCase):
    def test_uses_the_largest_two_units(self):
        cases = [(42, "42s"), (180, "3m"), (3_900, "1h 5m"), (93_600, "1d 2h")]

        for seconds, expected in cases:
            with self.subTest(seconds=seconds):
                self.assertEqual(duration(seconds), expected)
