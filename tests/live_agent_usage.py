"""Network-backed smoke test against the real providers.

Run with `make test-live`; it is deliberately outside tests/ so the offline
suite stays hermetic. It probes the built-in provider set rather than your
installed plugin file, so it checks the adapters, not your composition.
"""

import re
import unittest

from agent_usage.cli import fetch_provider_results, render
from builtins_fixture import EXTENSIONS


class LiveProvidersTest(unittest.TestCase):
    def test_live_providers_produce_flat_output_and_local_activity(self):
        results = fetch_provider_results(EXTENSIONS)
        output = render(results, EXTENSIONS)

        for extension in EXTENSIONS:
            self.assertIn(extension.name, output)

        for line in output.split("\n"):
            self.assertIsNone(re.match(r"^--[^-]", line), line)

        for result in results:
            self.assertIsNone(result.error, f"{result.name} live probe failed")

        for result in results:
            if result.extension_id == "deepseek":
                self.assertEqual(len(result.activity), 2)
                continue

            labels = {window.label for window in result.activity}
            self.assertIn("Weekly", labels, result.name)
            self.assertIn("5-hour", labels, result.name)


if __name__ == "__main__":
    unittest.main()
