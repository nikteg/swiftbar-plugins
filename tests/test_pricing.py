import os
import tempfile
import time
import unittest
import urllib.error

from agent_usage.pricing import codex, openai

MARKDOWN = """
### Standard pricing data
| Model | Short context input | Short context cached input | Short context cache writes | Short context output | Long context input | Long context cached input | Long context cache writes | Long context output |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-fixture (<272K context length) | $2.00 | - | $2.50 | $8.00 | $4.00 | - | $5.00 | $12.00 |
| gpt-5.5 | $1.00 | $0.10 | $1.25 | $4.00 | - | - | - | - |
### Batch pricing data
"""


def clear_caches():
    openai.load.cache_clear()
    codex.codex_prices.cache_clear()
    codex.credit_rates.cache_clear()
    codex._ranked_rates.cache_clear()
    codex.pricing_cache_version.cache_clear()


class PricingTableTest(unittest.TestCase):
    def test_parses_the_official_standard_pricing_table(self):
        prices = openai.parse_standard_prices(MARKDOWN)

        self.assertEqual(
            prices["gpt-fixture"].to_dict(),
            {
                "input": 2,
                # A dash means no cached discount, so cached tokens cost input.
                "cached_input": 2,
                "cache_write": 2.5,
                "output": 8,
                "long_context": {
                    "threshold_tokens": 272_000,
                    "input": 4,
                    "cached_input": 4,
                    "cache_write": 5,
                    "output": 12,
                },
            },
        )

    def test_omits_long_context_when_the_table_has_none(self):
        prices = openai.parse_standard_prices(MARKDOWN)

        self.assertIsNone(prices["gpt-5.5"].long_context)

    def test_rejects_a_missing_table(self):
        with self.assertRaises(ValueError):
            openai.parse_standard_prices("no table here")


class PriceCacheTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.original_path = openai.CACHE_PATH
        openai.CACHE_PATH = os.path.join(self.directory, "openai-prices.json")
        self.original_fetch = openai.fetch
        self.fetches = 0
        clear_caches()

    def tearDown(self):
        openai.CACHE_PATH = self.original_path
        openai.fetch = self.original_fetch
        clear_caches()

    def stub_fetch(self, markdown=MARKDOWN, error=None):
        def fetch():
            self.fetches += 1

            if error is not None:
                raise error

            return openai.parse_standard_prices(markdown)

        openai.fetch = fetch

    def test_fetches_and_caches_when_nothing_is_stored(self):
        self.stub_fetch()

        self.assertIn("gpt-fixture", openai.load())
        self.assertEqual(self.fetches, 1)
        self.assertTrue(os.path.exists(openai.CACHE_PATH))

    def test_reuses_a_fresh_cache_without_fetching(self):
        self.stub_fetch()
        openai.write_cache(openai.parse_standard_prices(MARKDOWN))

        self.assertIn("gpt-fixture", openai.load())
        self.assertEqual(self.fetches, 0)

    def test_refetches_once_the_cache_is_older_than_the_max_age(self):
        self.stub_fetch()
        openai.write_cache(openai.parse_standard_prices(MARKDOWN))
        stale = time.time() - openai.MAX_AGE_SECONDS - 1
        os.utime(openai.CACHE_PATH, (stale, stale))

        openai.load()

        self.assertEqual(self.fetches, 1)

    def test_serves_a_stale_cache_when_the_fetch_fails(self):
        openai.write_cache(openai.parse_standard_prices(MARKDOWN))
        stale = time.time() - openai.MAX_AGE_SECONDS - 1
        os.utime(openai.CACHE_PATH, (stale, stale))
        self.stub_fetch(error=urllib.error.URLError("offline"))

        self.assertIn("gpt-fixture", openai.load())

    def test_degrades_to_no_prices_when_there_is_no_cache_and_no_network(self):
        self.stub_fetch(error=urllib.error.URLError("offline"))

        self.assertEqual(openai.load(), {})

    def test_ignores_a_corrupt_cache(self):
        os.makedirs(os.path.dirname(openai.CACHE_PATH), exist_ok=True)

        with open(openai.CACHE_PATH, "w", encoding="utf-8") as handle:
            handle.write("{not json")

        self.stub_fetch()

        self.assertIn("gpt-fixture", openai.load())
        self.assertEqual(self.fetches, 1)


class CodexCreditsTest(PriceCacheTest):
    def setUp(self):
        super().setUp()
        self.stub_fetch()

    def test_converts_token_counts_to_credits_at_25_per_usd(self):
        # gpt-5.5 input is $1.00 per million, so a million tokens is 25 credits.
        self.assertEqual(codex.codex_credits("gpt-5.5", 1_000_000, 0, 0), 25)

    def test_falls_back_to_the_default_model_for_unknown_names(self):
        self.assertEqual(
            codex.codex_credits("unknown-future-model", 1_000_000, 0, 0),
            codex.codex_credits(codex.CODEX_FALLBACK_MODEL, 1_000_000, 0, 0),
        )

    def test_uses_long_context_rates_past_the_threshold(self):
        tokens = openai.LONG_CONTEXT_THRESHOLD_TOKENS + 1

        short = codex.codex_credits("gpt-fixture", 1000, 0, 0)
        long = codex.codex_credits(
            "gpt-fixture", 1000, 0, 0, context_input_tokens=tokens
        )

        self.assertEqual(long, short * 2)  # Long-context input is $4 against $2.

    def test_reports_no_credits_when_no_prices_are_available(self):
        clear_caches()
        self.stub_fetch(error=urllib.error.URLError("offline"))

        self.assertEqual(codex.codex_credits("gpt-5.5", 1_000_000, 0, 0), 0.0)

    def test_pricing_version_changes_with_the_table(self):
        first = codex.pricing_cache_version()
        clear_caches()
        os.remove(openai.CACHE_PATH)  # Otherwise the fresh cache wins over the fetch.
        self.stub_fetch(markdown=MARKDOWN.replace("$2.00", "$3.00"))

        self.assertNotEqual(first, codex.pricing_cache_version())


if __name__ == "__main__":
    unittest.main()
