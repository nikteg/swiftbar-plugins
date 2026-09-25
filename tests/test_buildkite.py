import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from unittest import mock

from ci import buildkite
from ci.menu import View, WorkflowRun
from ci.runs import DEFAULT_COLORS, diagnose
from plugin_loader import load
from swiftbar_lib.output import render

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
BK = "/opt/homebrew/bin/bk"


def job(job_id, state, name="Test", **extra):
    return {
        "id": job_id,
        "type": "script",
        "name": name,
        "state": state,
        "web_url": f"https://buildkite.com/acme/web-app/builds/7#{job_id}",
        **extra,
    }


def raw(number=7, state="passed", jobs=(), **extra):
    return {
        "id": f"build-{number}",
        "number": number,
        "state": state,
        "web_url": f"https://buildkite.com/acme/web-app/builds/{number}",
        "commit": "abcdef1234567890",
        "branch": "main",
        "message": "Add a retry\n\nWith a body.",
        "source": "webhook",
        "creator": {"name": "Octo Cat"},
        "created_at": "2026-09-25T11:50:00.000Z",
        "started_at": "2026-09-25T11:50:05.000Z",
        "finished_at": None
        if state in ("running", "failing")
        else "2026-09-25T11:55:05.000Z",
        "pipeline": {
            "slug": "web-app",
            "name": "Web app",
            "repository": "git@github.com:acme/web-app.git",
            "web_url": "https://buildkite.com/acme/web-app",
        },
        "jobs": list(jobs),
        **extra,
    }


class ParseBuildTest(unittest.TestCase):
    def test_maps_build_states_to_the_menus_four(self):
        cases = [
            ("scheduled", "running"),
            ("running", "running"),
            ("failing", "failure"),
            ("failed", "failure"),
            ("passed", "success"),
            ("blocked", "success"),
            ("canceled", "other"),
            ("not_run", "other"),
        ]

        for status, expected in cases:
            with self.subTest(status=status):
                self.assertEqual(
                    buildkite.parse_build(raw(state=status), BK).state, expected
                )

    def test_files_a_build_under_its_github_repo_and_commit(self):
        build = buildkite.parse_build(raw(), BK)

        self.assertEqual(build.repo, "acme/web-app")
        self.assertEqual(
            build.commit_url, "https://github.com/acme/web-app/commit/abcdef1234567890"
        )
        self.assertEqual((build.workflow, build.title), ("Web app", "Add a retry"))

    def test_falls_back_to_the_pipeline_slug_off_github(self):
        pipeline = {"slug": "infra", "repository": "https://gitlab.com/acme/infra.git"}
        build = buildkite.parse_build(raw(pipeline=pipeline), BK)

        self.assertEqual((build.repo, build.commit_url), ("infra", None))

    def test_reads_github_remotes_in_both_forms(self):
        for remote in (
            "git@github.com:acme/web-app.git",
            "https://github.com/acme/web-app",
            "https://github.com/acme/web-app.git",
        ):
            with self.subTest(remote=remote):
                self.assertEqual(buildkite.github_repo(remote), "acme/web-app")

    def test_opens_the_first_hard_failed_job_log_in_terminal(self):
        jobs = [
            job("soft", "failed", soft_failed=True),
            job("hard", "failed"),
            job("next", "failed"),
        ]
        build = buildkite.parse_build(raw(state="failed", jobs=jobs), BK)

        self.assertEqual(
            build.log_command, (BK, "job", "log", "hard", "--no-timestamps")
        )

    def test_skips_a_build_without_a_pipeline(self):
        self.assertIsNone(buildkite.parse_build(raw(pipeline={}), BK))


class BuildsTest(unittest.TestCase):
    def fake_bk(self, answer):
        def bk_api(bk, path):
            if isinstance(answer, Exception):
                raise answer

            return json.dumps(answer)

        return mock.patch.object(buildkite, "bk_api", bk_api)

    def test_filters_builds_by_repo(self):
        other = {"slug": "infra", "repository": "git@github.com:acme/infra.git"}
        payload = [raw(1), raw(2, pipeline=other)]

        with self.fake_bk(payload):
            excluded = buildkite.builds(BK, [], ["acme/infra"], 10)
            only = buildkite.builds(BK, ["acme/infra"], [], 10)

        self.assertEqual([b.number for b in excluded.runs], [1])
        self.assertEqual([b.number for b in only.runs], [2])

    def test_reports_a_failed_call_as_an_error(self):
        with self.fake_bk(RuntimeError("Error: 401 Unauthorized")):
            found = buildkite.builds(BK, [], [], 10)

        self.assertEqual((found.runs, found.errors), ([], ["Error: 401 Unauthorized"]))


LOG = (
    "\x1b_bk;t=1\x07~~~ Preparing working directory\r\n"
    "\x1b_bk;t=2\x07$ git fetch\r\r\n"
    "\x1b_bk;t=3\x07--- Running tests\r\n"
    "\x1b_bk;t=4\x07------\r\r\n"
    "\x1b_bk;t=5\x07\x1b[31mexpected 2 to equal 3\x1b[0m\r\r\n"
    "\x1b_bk;t=6\x07^^^ +++\r\n"
    "\x1b_bk;t=7\x07\x1b[31m🚨 Error: The command exited with status 1\x1b[0m\r\n"
    "\x1b_bk;t=8\x07user command error: exit status 1\r\n"
)


class DiagnoseTest(unittest.TestCase):
    def setUp(self):
        cache = tempfile.TemporaryDirectory()
        self.addCleanup(cache.cleanup)
        patch = mock.patch.dict(os.environ, {"SWIFTBAR_PLUGIN_CACHE_PATH": cache.name})
        patch.start()
        self.addCleanup(patch.stop)

    def test_keeps_output_up_to_the_agents_error_without_group_headers(self):
        self.assertEqual(
            buildkite.log_tail(LOG),
            [
                "$ git fetch",
                "------",
                "expected 2 to equal 3",
                "🚨 Error: The command exited with status 1",
            ],
        )

    def test_reads_each_failed_job_once(self):
        failed_build = raw(
            state="failed",
            jobs=[job("j1", "passed"), job("j2", "failed", exit_status=1)],
        )
        build = buildkite.parse_build(failed_build, BK)
        calls = []

        def bk_api(bk, path):
            calls.append(path)

            return json.dumps(failed_build if path.endswith("/7") else {"content": LOG})

        def read(run):
            return buildkite.failed_jobs(BK, run)

        with mock.patch.object(buildkite, "bk_api", bk_api):
            first = diagnose("buildkite", [build], read)
            second = diagnose("buildkite", [build], read)

        self.assertEqual(
            calls,
            ["/pipelines/web-app/builds/7", "/pipelines/web-app/builds/7/jobs/j2/log"],
        )
        self.assertEqual(first, second)
        (failed_job,) = first["build-7"]
        self.assertEqual((failed_job.name, failed_job.step), ("Test", "exit 1"))

    def test_says_build_and_pipeline_in_the_links(self):
        build = buildkite.parse_build(raw(), BK)
        output = render(
            WorkflowRun(build, View(NOW, DEFAULT_COLORS, nouns=("build", "pipeline")))
        )

        self.assertIn(
            "--Open build | href=https://buildkite.com/acme/web-app/builds/7", output
        )
        self.assertIn(
            "--Open pipeline | href=https://buildkite.com/acme/web-app", output
        )


class PluginTest(unittest.TestCase):
    def test_loads_without_running(self):
        self.assertEqual(load("buildkite.5m.py").PLUGIN, "buildkite")
