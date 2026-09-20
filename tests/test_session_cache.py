import json
import os
import shutil
import tempfile
import time
import unittest

from agent_usage.session_cache import (
    SESSION_CACHE_FILENAMES,
    JsonlCache,
    clear_session_caches,
)


class JsonlCacheTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="agent-usage-cache-")
        self.session = os.path.join(self.directory, "session.jsonl")
        self.cache_path = os.path.join(self.directory, "cache", "session.json")
        self.now = time.time() * 1000
        self.parsed = 0
        self.addCleanup(shutil.rmtree, self.directory, True)

    def collect(self, version="fixture-v1"):
        def parse(record, state):
            self.parsed += 1

            return state, record

        cache = JsonlCache(
            cache_path=self.cache_path,
            version=version,
            now=self.now,
            retention_ms=7 * 86_400_000,
            parse=parse,
            encode_event=lambda event: event,
            decode_event=lambda value: value if _is_event(value) else None,
            event_timestamp=lambda event: event["timestamp"],
        )

        return [event["value"] for event in cache.events([self.session])]

    def append(self, value, timestamp=None, mode="a"):
        record = {
            "timestamp": self.now if timestamp is None else timestamp,
            "value": value,
        }

        with open(self.session, mode, encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    def test_reuses_unchanged_files_and_parses_only_appended_records(self):
        self.append(1, self.now - 1_000, mode="w")
        self.assertEqual(self.collect(), [1])
        self.assertEqual(self.parsed, 1)

        self.parsed = 0
        self.assertEqual(self.collect(), [1])
        self.assertEqual(self.parsed, 0)

        self.append(2)
        self.assertEqual(self.collect(), [1, 2])
        self.assertEqual(self.parsed, 1)

        self.parsed = 0
        self.append(3, mode="w")
        self.assertEqual(self.collect(), [3])
        self.assertEqual(self.parsed, 1)

        self.parsed = 0
        self.assertEqual(self.collect("fixture-v2"), [3])
        self.assertEqual(self.parsed, 1)

    def test_ignores_incomplete_trailing_records(self):
        with open(self.session, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": self.now, "value": 1}) + "\n")
            handle.write('{"timestamp": ')

        self.assertEqual(self.collect(), [1])

    def test_skips_corrupt_records(self):
        with open(self.session, "w", encoding="utf-8") as handle:
            handle.write("not json\n")
            handle.write(json.dumps({"timestamp": self.now, "value": 7}) + "\n")

        self.assertEqual(self.collect(), [7])

    def test_drops_events_older_than_the_retention_window(self):
        self.append(1, self.now - 30 * 86_400_000, mode="w")
        self.assertEqual(self.collect(), [])

    def test_survives_a_missing_file(self):
        self.assertEqual(self.collect(), [])


class ClearCachesTest(unittest.TestCase):
    def test_clears_only_plugin_owned_caches(self):
        directory = tempfile.mkdtemp(prefix="agent-usage-clear-")
        self.addCleanup(shutil.rmtree, directory, True)
        unrelated = os.path.join(directory, "keep-me.json")
        names = list(SESSION_CACHE_FILENAMES) + [
            "claude-sessions-fixture.json",
            "keep-me.json",
        ]

        for name in names:
            with open(os.path.join(directory, name), "w", encoding="utf-8") as handle:
                handle.write("cached\n")

        self.assertEqual(clear_session_caches(directory), 3)
        self.assertTrue(os.path.exists(unrelated))
        self.assertEqual(clear_session_caches(directory), 0)

    def test_tolerates_a_missing_directory(self):
        self.assertEqual(clear_session_caches("/nonexistent/agent-usage"), 0)


def _is_event(value):
    return (
        isinstance(value, dict)
        and isinstance(value.get("timestamp"), (int, float))
        and isinstance(value.get("value"), (int, float))
    )


if __name__ == "__main__":
    unittest.main()
