import unittest
from datetime import UTC, datetime

from agent_usage.utils import (
    clamp_percent,
    clean_error,
    compact_number,
    number_value,
    parse_date,
    reset_from_window,
    swiftbar_escape,
    usage_meter,
)


class NumberTest(unittest.TestCase):
    def test_formats_compact_numbers(self):
        self.assertEqual(
            [
                compact_number(value)
                for value in (0, 999, 1_000, 12_345, 4_600, 2_500_000)
            ],
            ["0", "999", "1K", "12.3K", "4.6K", "2.5M"],
        )

    def test_reads_numbers_from_strings(self):
        self.assertEqual(number_value("20000"), 20_000)
        self.assertIsNone(number_value(""))
        self.assertIsNone(number_value("abc"))
        self.assertIsNone(number_value(None))
        self.assertIsNone(number_value(True))

    def test_clamps_percentages(self):
        self.assertEqual(
            [clamp_percent(value) for value in (-5, 50, 150)], [0, 50, 100]
        )


class DateTest(unittest.TestCase):
    def test_parses_iso_strings(self):
        self.assertEqual(
            parse_date("2030-01-01T00:00:00Z"),
            datetime(2030, 1, 1, tzinfo=UTC),
        )

    def test_parses_epoch_seconds_and_milliseconds(self):
        self.assertEqual(parse_date(1_788_220_800), parse_date(1_788_220_800_000))

    def test_rejects_unusable_values(self):
        for value in (None, "", "not a date", True, []):
            self.assertIsNone(parse_date(value))

    def test_resolves_relative_reset_windows(self):
        absolute = reset_from_window({"reset_at": 1_788_220_800})
        self.assertEqual(absolute.isoformat(), "2026-09-01T00:00:00+00:00")
        relative = reset_from_window({"reset_after_seconds": 60})
        self.assertGreater(relative, datetime.now(UTC))
        self.assertIsNone(reset_from_window(None))


class MeterTest(unittest.TestCase):
    def test_builds_a_meter_from_utilization_or_percent(self):
        self.assertEqual(usage_meter("Weekly", {"utilization": 120}).used_percent, 100)
        self.assertEqual(usage_meter("Weekly", {"percent": 7}).used_percent, 7)
        self.assertIsNone(usage_meter("Weekly", {"other": 7}))
        self.assertIsNone(usage_meter("Weekly", None))


class TextTest(unittest.TestCase):
    def test_strips_control_characters_and_pipes(self):
        self.assertEqual(
            swiftbar_escape("Kimi\x1b[31m| bash=/bin/false\nInjected"),
            "Kimi [31m  bash=/bin/false Injected",
        )

    def test_shortens_and_flattens_error_messages(self):
        self.assertEqual(clean_error(RuntimeError("a|b\nc")), "a b c")
        self.assertEqual(clean_error(TimeoutError()), "Request timed out")
        self.assertEqual(len(clean_error(RuntimeError("x" * 200))), 100)


if __name__ == "__main__":
    unittest.main()
