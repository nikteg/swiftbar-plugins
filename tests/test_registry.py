import json
import os
import shutil
import tempfile
import unittest

import builtins_fixture
from agent_usage.provider import (
    CustomSecret,
    EnvSecret,
    JsonFileSecret,
    ValueSecret,
    api_key_auth,
    custom_auth,
    custom_quota,
    define_provider,
    http_json_quota,
    no_auth,
)
from agent_usage.registry import collect_provider_results
from agent_usage.types import Meter, ProviderExtension, ProviderResult


def _fixture(collect) -> ProviderExtension:
    return ProviderExtension(
        id="fixture",
        name="Fixture Provider",
        auth_type="api-key",
        account_type="api",
        quota_type="reported",
        collect=collect,
    )


class RegistryTest(unittest.TestCase):
    def test_collects_extensions_independently(self):
        results = collect_provider_results(
            [
                _fixture(
                    lambda: ProviderResult(name="Fixture Provider", subtitle="READY")
                )
            ]
        )
        self.assertEqual(
            [(r.name, r.subtitle, r.extension_id) for r in results],
            [("Fixture Provider", "READY", "fixture")],
        )

    def test_turns_a_failing_collector_into_an_error_row(self):
        def explode():
            raise RuntimeError("boom|with\nmarkup")

        results = collect_provider_results(
            [_fixture(explode), _fixture(lambda: ProviderResult(name="Second"))]
        )
        self.assertEqual(results[0].error, "boom with markup")
        self.assertEqual(results[1].name, "Second")

    def test_returns_nothing_without_extensions(self):
        self.assertEqual(collect_provider_results([]), [])


class ProviderAdapterTest(unittest.TestCase):
    def test_drives_auth_and_quota_collection_from_adapters(self):
        extension = define_provider(
            id="adapter-fixture",
            name="Adapter Fixture",
            account_type="api",
            auth=api_key_auth(source=ValueSecret("secret"), scheme="Bearer"),
            quota=custom_quota(
                "reported",
                lambda headers: ProviderResult(
                    name="",
                    subtitle=headers["Authorization"],
                    meters=[Meter("Weekly", 25)],
                ),
            ),
        )
        result = extension.collect()
        self.assertEqual(
            (extension.auth_type, extension.account_type, extension.quota_type),
            ("api-key", "api", "reported"),
        )
        self.assertEqual(
            (result.name, result.subtitle, result.meters[0].used_percent),
            ("Adapter Fixture", "Bearer secret", 25),
        )

    def test_reports_a_missing_secret(self):
        extension = define_provider(
            id="adapter-fixture",
            name="Adapter Fixture",
            account_type="api",
            auth=api_key_auth(
                source=ValueSecret(""), missing_message="No API key in Pi auth"
            ),
            quota=custom_quota("reported", lambda _headers: ProviderResult(name="")),
        )
        self.assertEqual(extension.collect().error, "No API key in Pi auth")

    def test_degrades_to_a_partial_result_on_a_quota_error(self):
        def parse(_body, _headers):  # pragma: no cover - never reached
            raise AssertionError("request should not succeed")

        quota = http_json_quota(
            type="activity",
            url="https://127.0.0.1:9/never",
            parse=parse,
            on_error=lambda _error: ProviderResult(name="", subtitle="OFFLINE"),
        )
        result = quota.collect({})
        self.assertEqual(result.subtitle, "OFFLINE")
        self.assertTrue(result.error)


class SecretSourceTest(unittest.TestCase):
    def test_resolves_every_built_in_source(self):
        directory = tempfile.mkdtemp(prefix="agent-usage-secret-")
        self.addCleanup(shutil.rmtree, directory, True)
        path = os.path.join(directory, "auth.json")

        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"deepseek": {"key": "from-file"}}, handle)

        os.environ["AGENT_USAGE_FIXTURE_KEY"] = "from-env"
        self.addCleanup(os.environ.pop, "AGENT_USAGE_FIXTURE_KEY", None)

        self.assertEqual(EnvSecret("AGENT_USAGE_FIXTURE_KEY").resolve(), "from-env")
        self.assertIsNone(EnvSecret("AGENT_USAGE_MISSING_KEY").resolve())
        self.assertEqual(ValueSecret("literal").resolve(), "literal")
        self.assertEqual(CustomSecret(lambda: "computed").resolve(), "computed")
        self.assertEqual(
            JsonFileSecret(path, ["deepseek", "key"]).resolve(), "from-file"
        )
        self.assertIsNone(JsonFileSecret(path, ["deepseek", "missing"]).resolve())
        self.assertIsNone(JsonFileSecret("/nonexistent.json", ["a"]).resolve())


class AuthAdapterTest(unittest.TestCase):
    def test_passes_static_headers_through_without_auth(self):
        self.assertEqual(
            no_auth({"Accept": "application/json"}).authorize(),
            {"Accept": "application/json"},
        )
        self.assertEqual(no_auth().type, "none")

    def test_wraps_a_custom_authorize_callable(self):
        adapter = custom_auth("oauth", lambda: {"Authorization": "Bearer live"})
        self.assertEqual(
            (adapter.type, adapter.authorize()),
            ("oauth", {"Authorization": "Bearer live"}),
        )


class BuiltInProvidersTest(unittest.TestCase):
    def test_declares_auth_account_and_quota_types(self):
        self.assertEqual(
            [
                (e.name, e.auth_type, e.account_type, e.quota_type)
                for e in builtins_fixture.EXTENSIONS
            ],
            [
                ("Claude Code", "oauth", "subscription", "reported"),
                ("Codex", "oauth", "hybrid", "hybrid"),
                ("Kimi Code", "oauth", "subscription", "reported"),
                ("DeepSeek", "api-key", "api", "activity"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
