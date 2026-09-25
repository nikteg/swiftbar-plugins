import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from unittest import mock

from plugin_loader import load
from swiftbar_lib import config
from swiftbar_lib.output import render

plugin = load("github-actions.1m.py")

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
GH = "/opt/homebrew/bin/gh"


def raw(run_id, created, status="completed", conclusion="success", **extra):
    return {
        "id": run_id,
        "html_url": f"https://github.com/o/r/actions/runs/{run_id}",
        "name": "CI",
        "display_title": "Fix the thing",
        "head_sha": f"sha{run_id}",
        "head_commit": {"message": "Fix the thing\n\nWith a body."},
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
    return plugin.parse_run(repo, raw(**fields))


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
        self.assertIsNone(plugin.parse_run("o/r", {"name": "CI"}))

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

        return mock.patch.object(plugin, "gh_api", gh_api)

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
            found = plugin.latest(GH, [], discover=10, exclude=[], limit=2, actor=None)

        self.assertEqual([(r.repo, r.id) for r in found.runs], [("o/a", 1), ("o/b", 3)])
        self.assertEqual(found.errors, [])

    def test_skips_excluded_repos_and_still_discovers_enough(self):
        requested = []
        empty = json.dumps({"workflow_runs": []})

        def gh_api(gh, path, *flags):
            requested.append(path)

            return "o/a\no/skip\no/b\n" if path.startswith("user/repos") else empty

        with mock.patch.object(plugin, "gh_api", gh_api):
            plugin.latest(GH, [], discover=2, exclude=["o/skip"], limit=5, actor=None)

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
            found = plugin.latest(
                GH, ["o/a", "o/b"], discover=10, exclude=[], limit=5, actor=None
            )

        self.assertEqual([r.id for r in found.runs], [1])
        self.assertEqual(found.errors, ["o/b: gh: Not Found (HTTP 404)"])

    def test_reports_a_failed_discovery_as_the_only_error(self):
        with self.fake_gh({"user/repos": RuntimeError("not logged in")}):
            found = plugin.latest(GH, [], discover=10, exclude=[], limit=5, actor=None)

        self.assertEqual((found.runs, found.errors), ([], ["not logged in"]))


class RenderTest(unittest.TestCase):
    def test_draws_a_square_per_run_with_a_commits_runs_side_by_side(self):
        runs = [
            run(run_id=1, created="2026-09-25T11:50:00Z", status="in_progress"),
            run(run_id=2, created="2026-09-25T11:45:00Z", head_sha="sha1"),
            run(run_id=3, created="2026-09-25T11:40:00Z", conclusion="failure"),
        ]
        title = render(plugin.Squares(runs)).split("\n")[0]

        self.assertTrue(
            title.startswith("\x1b[33m■\x1b[0m\x1b[32m■\x1b[0m \x1b[31m■\x1b[0m |"),
            title,
        )

    def test_draws_a_grey_square_when_there_are_no_runs(self):
        self.assertTrue(render(plugin.Squares([])).startswith("\x1b[90m■\x1b[0m |"))

    def test_heads_each_commit_over_its_runs(self):
        runs = [
            run(run_id=1, created="2026-09-25T11:50:00Z", head_sha="abcdef123456"),
            run(run_id=2, created="2026-09-25T11:45:00Z", head_sha="abcdef123456"),
            run(run_id=3, created="2026-09-25T11:40:00Z"),
        ]
        output = render(plugin.Repo("o/r", runs, {}, GH, NOW))
        body = output.partition("---\n")[2]
        lines = [line.split(" | ")[0] for line in body.split("\n")]

        self.assertEqual(
            [line for line in lines if not line.startswith("--")],
            [
                "o/r",
                "\x1b[32m■\x1b[0m \x1b[90mabcdef1 · main · Fix the thing\x1b[0m",
                "\x1b[90m  └\x1b[0m \x1b[32m■\x1b[0m CI · 5m ago",
                "\x1b[90m  └\x1b[0m \x1b[32m■\x1b[0m CI · 5m ago",
                "\x1b[32m■\x1b[0m \x1b[90msha3 · main · Fix the thing\x1b[0m",
                "\x1b[90m  └\x1b[0m \x1b[32m■\x1b[0m CI · 5m ago",
            ],
        )
        self.assertIn("href=https://github.com/o/r/commit/abcdef123456", output)

    def test_groups_runs_under_their_repo_in_order_of_the_newest(self):
        runs = [
            run(repo="o/a", run_id=1, created="2026-09-25T11:50:00Z"),
            run(repo="o/b", run_id=2, created="2026-09-25T11:40:00Z"),
            run(repo="o/a", run_id=3, created="2026-09-25T11:30:00Z"),
        ]
        output = render(
            [
                plugin.Repo(repo, grouped, {}, GH, NOW)
                for repo, grouped in plugin.grouped(runs, lambda r: r.repo).items()
            ]
        )
        headings = [line for line in output.split("\n") if "size=13" in line]

        self.assertEqual(
            headings,
            [
                "o/a | font=Menlo size=13 href=https://github.com/o/a/actions",
                "o/b | font=Menlo size=13 href=https://github.com/o/b/actions",
            ],
        )

        self.assertLess(output.index("runs/3"), output.index("o/b |"))

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
                self.assertEqual(plugin.overall(runs), state)

    def test_details_a_run_in_its_submenu(self):
        running = run(run_id=7, created="2026-09-25T11:57:00Z", status="in_progress")
        output = render(plugin.WorkflowRun(running, None, GH, NOW))

        self.assertIn(
            "\x1b[90m  └\x1b[0m \x1b[33m■\x1b[0m CI · running 3m | "
            "href=https://github.com/o/r/actions/runs/7 ansi=true",
            output,
        )
        self.assertIn(
            "--#7 · push by me | font=Menlo\n--In progress for 3m | font=Menlo", output
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
            plugin.log_tail(LOG),
            [
                "✖ 1 test failed",
                "expected 2 to equal 3",
                "Process completed with exit code 1.",
            ],
        )

    def test_keeps_only_the_last_lines(self):
        self.assertEqual(
            plugin.log_tail(LOG, count=1), ["Process completed with exit code 1."]
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

        with mock.patch.object(plugin, "gh_api", gh_api):
            first = plugin.diagnose(GH, [failed])
            second = plugin.diagnose(GH, [failed])

        self.assertEqual(
            calls, ["repos/o/r/actions/runs/9/jobs", "repos/o/r/actions/jobs/2/logs"]
        )
        self.assertEqual(first, second)
        (job,) = first[9]
        self.assertEqual((job.name, job.step), ("test", "Run tests"))
        self.assertEqual(job.log[-1], "Process completed with exit code 1.")

    def test_reports_an_unreadable_log_and_tries_again_next_time(self):
        failed = run(run_id=9, created="2026-09-25T11:50:00Z", conclusion="failure")

        def gh_api(gh, path, *flags):
            raise RuntimeError("gh: Gone (HTTP 410)")

        with mock.patch.object(plugin, "gh_api", gh_api):
            self.assertEqual(plugin.diagnose(GH, [failed]), {9: "gh: Gone (HTTP 410)"})

        self.assertEqual(plugin.state.load("github-actions", "failures.json"), {})

    def test_renders_the_failed_step_over_its_log(self):
        failed = run(run_id=9, created="2026-09-25T11:50:00Z", conclusion="failure")
        job = plugin.FailedJob(
            name="test",
            step="Run tests",
            url="https://github.com/o/r/actions/runs/9/job/2",
            log=["--- FAIL: TestThing", "exit code 1"],
        )
        output = render(plugin.WorkflowRun(failed, [job], GH, NOW))

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
        running = configured.parse_run(
            "o/r", raw(1, "2026-09-25T11:50:00Z", status="in_progress")
        )

        self.assertEqual(configured.Square(running), "\x1b[38;5;208m■\x1b[0m")
        self.assertEqual(configured.COLORS["failure"], "critical")


class DurationTest(unittest.TestCase):
    def test_uses_the_largest_two_units(self):
        cases = [(42, "42s"), (180, "3m"), (3_900, "1h 5m"), (93_600, "1d 2h")]

        for seconds, expected in cases:
            with self.subTest(seconds=seconds):
                self.assertEqual(plugin.duration(seconds), expected)
