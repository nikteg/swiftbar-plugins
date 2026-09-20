"""Network-backed smoke test against the real providers.

Run with `make test-live`; it lives outside the names pytest collects by
default so the offline suite stays hermetic. It checks the adapters, not any
particular plugin's composition.
"""

import unittest

from agent_usage import collect
from builtins_fixture import EXTENSIONS


class LiveProvidersTest(unittest.TestCase):
    def test_every_provider_reports_without_error(self):
        for usage in collect(*EXTENSIONS):
            with self.subTest(provider=usage.provider.name):
                self.assertIsNone(usage.result.error)

    def test_every_provider_reports_some_quota_or_activity(self):
        for usage in collect(*EXTENSIONS):
            with self.subTest(provider=usage.provider.name):
                self.assertTrue(
                    usage.result.meters or usage.result.activity,
                    "no quota and no local activity",
                )
