import re
import unittest
from datetime import UTC, datetime, timedelta

from agent_usage.types import (
    ActivityExtension,
    ActivityWindow,
    DetailLine,
    LocalBudgetInfo,
    Meter,
    ProviderExtension,
    ProviderResult,
    Usage,
)
from builtins_fixture import EXTENSIONS
from builtins_fixture import LOCAL_ACTIVITY_BUDGETS as BUDGETS
from plugin_loader import load
from swiftbar_lib.components import Action, Indicators
from swiftbar_lib.output import render
from swiftbar_lib.ui import Separator

plugin = load("agent-usage.15m.py")
Icon, ProviderUsage = plugin.Icon, plugin.ProviderUsage


def pair(result, providers):
    """Finds a result's provider.

    A plugin file names both and pairs them by hand; these tests build results
    from fixtures, so they look the provider up instead.
    """
    by_id = next((e for e in providers if e.id == result.extension_id), None)

    return by_id or next((e for e in providers if e.name == result.name), None)


def show(results, extensions=None, plugin_path="/plugin/agent-usage.15m.py"):
    """Assembles the menu the way a plugin file does, then renders it."""
    providers = EXTENSIONS if extensions is None else extensions
    paired = [Usage(pair(result, providers), result) for result in results]

    return render(
        [
            Indicators(*(Icon(usage) for usage in paired)),
            [[ProviderUsage(usage), Separator()] for usage in paired],
            Action("Clear local usage caches", plugin_path, "--clear-cache"),
        ]
    )


class TitleTest(unittest.TestCase):
    def test_renders_a_valid_swiftbar_title_and_menu(self):
        output = show([ProviderResult(name="Codex", meters=[Meter("Weekly", 40)])])
        self.assertTrue(output.startswith("\x1b[32m●\x1b[0m | ansi=true"), output)
        self.assertIn("font=Menlo size=13", output.split("\n")[0])
        self.assertIn("\x1b[32m●\x1b[0m Codex | ansi=true", output)
        self.assertNotIn("--Weekly", output)

    def test_renders_filled_circles_colored_by_usage_state(self):
        results = [
            ProviderResult(
                name="Claude Default",
                meters=[Meter("Weekly", 80), Meter("5-hour", 10)],
            ),
            ProviderResult(name="Claude Personal", meters=[Meter("Weekly", 20)]),
            ProviderResult(
                name="Codex",
                activity=[
                    ActivityWindow("Weekly", 12_000_000, 4_000_000, 1, credits=500),
                    ActivityWindow("5-hour", 2_000_000, 800_000, 1, credits=100),
                ],
            ),
            ProviderResult(name="Kimi Code", error="logged out"),
            ProviderResult(
                name="DeepSeek",
                activity=[
                    ActivityWindow("Weekly", 100, 100, 1, cost=4.6),
                    ActivityWindow("5-hour", 50, 50, 1, cost=0.2),
                ],
            ),
        ]
        expected = " ".join(f"\x1b[{color}m●\x1b[0m" for color in (33, 32, 33, 31, 31))
        self.assertTrue(show(results).split("\n")[0].startswith(expected))


class ResetTest(unittest.TestCase):
    def test_renders_a_relative_countdown(self):
        resets_at = datetime.now(UTC) + timedelta(hours=3, minutes=20)
        output = show(
            [ProviderResult(name="Fixture", meters=[Meter("5-hour", 20, resets_at)])]
        )
        self.assertIn("(in 3h 20m)", output)

    def test_includes_the_date_beyond_today(self):
        resets_at = datetime.now(UTC) + timedelta(days=2, hours=3)
        local = resets_at.astimezone()
        output = show(
            [ProviderResult(name="Fixture", meters=[Meter("Monthly", 20, resets_at)])]
        )
        expected = "resets {} {} {}".format(
            local.strftime("%a"), local.strftime("%b"), local.day
        )
        self.assertIn(expected, output)

    def test_reports_a_due_reset(self):
        resets_at = datetime.now(UTC) - timedelta(minutes=1)
        output = show(
            [ProviderResult(name="Fixture", meters=[Meter("5-hour", 20, resets_at)])]
        )
        self.assertIn("reset due", output)


class MenuActionTest(unittest.TestCase):
    def test_renders_the_cache_clearing_action(self):
        output = show(
            [ProviderResult(name="Fixture")],
            extensions=[],
        )
        self.assertIn(
            "Clear local usage caches | bash=/plugin/agent-usage.15m.py "
            "param1=--clear-cache terminal=false refresh=true",
            output,
        )

    def test_quotes_a_plugin_path_containing_spaces(self):
        output = show(
            [ProviderResult(name="Fixture")],
            extensions=[],
            plugin_path="/Application Support/SwiftBar/agent-usage.15m.py",
        )

        self.assertIn('bash="/Application Support/SwiftBar/agent-usage.15m.py"', output)


class SanitizeTest(unittest.TestCase):
    def test_sanitizes_provider_controlled_markup(self):
        output = show(
            [
                ProviderResult(
                    name="Kimi Code",
                    subtitle="Moderato\x1b[31m| href=https://example.invalid\nInjected",
                    meters=[
                        Meter(
                            "Weekly\x1b[31m| bash=/bin/false",
                            10,
                            detail="10/100| href=https://example.invalid",
                        )
                    ],
                )
            ]
        )
        self.assertNotIn("\x1b[31m", output)

        for line in output.split("\n"):
            self.assertLessEqual(len(re.findall(r"\|", line)), 1, line)


class ActivityTest(unittest.TestCase):
    def test_renders_local_activity_as_a_dark_gray_companion_row(self):
        output = show(
            [
                ProviderResult(
                    name="Codex",
                    activity=[ActivityWindow("Weekly", 1_000, 200, 3, credits=1)],
                )
            ]
        )
        self.assertIn(
            "\x1b[90m  └\x1b[0m \x1b[90m1K processed tokens · 200 uncached tokens · 3 calls"
            " · 1 credits ≈ $0.04 · local activity",
            output,
        )
        self.assertEqual(BUDGETS["codex"]["weekly_credits"], 4_600)
        self.assertIn(
            "budget 4.6K credits ≈ $184\x1b[0m | ansi=true font=Menlo", output
        )

    def test_renders_the_monthly_activity_budget(self):
        output = show(
            [
                ProviderResult(
                    name="Codex",
                    activity=[ActivityWindow("Monthly", 1_000, 200, 3, credits=1)],
                )
            ]
        )
        self.assertIn("Monthly: ○○○○○○○○○○○○ 0% used", output)
        self.assertIn("budget 20K credits ≈ $800\x1b[0m | ansi=true font=Menlo", output)

    def test_places_activity_directly_after_its_matching_meter(self):
        output = show(
            [
                ProviderResult(
                    name="Fixture",
                    meters=[
                        Meter("Weekly", 20),
                        Meter("5-hour", 30),
                        Meter("Model weekly", 40),
                    ],
                    activity=[
                        ActivityWindow("Weekly", 1_000, 100, 2),
                        ActivityWindow("5-hour", 500, 50, 1),
                    ],
                )
            ]
        )
        lines = output.split("\n")
        weekly = _index(lines, "Weekly: ●●○○○○○○○○○○ 20% used")
        five_hour = _index(lines, "5-hour: ●●●●○○○○○○○○ 30% used")
        self.assertEqual(_index(lines, "1K processed tokens"), weekly + 1)
        self.assertEqual(_index(lines, "500 processed tokens"), five_hour + 1)

    def test_combines_reported_monthly_usage_with_local_activity(self):
        resets_at = datetime(2030, 9, 1, tzinfo=UTC)
        output = show(
            [
                ProviderResult(
                    name="Codex",
                    meters=[Meter("Monthly", 25, resets_at, detail="5K/20K credits")],
                    activity=[
                        ActivityWindow(
                            "Monthly", 1_000, 200, 3, credits=1, resets_at=resets_at
                        )
                    ],
                )
            ]
        )
        monthly = [line for line in output.split("\n") if "Monthly:" in line]
        self.assertEqual(len(monthly), 1)
        self.assertIn("5K/20K credits", monthly[0])
        self.assertIn("1 credits ≈ $0.04 · local activity", output)

    def test_renders_configured_budgets_inline(self):
        output = show(
            [
                ProviderResult(
                    name="DeepSeek",
                    activity=[ActivityWindow("5-hour", 1_000, 200, 3, cost=0.5)],
                )
            ]
        )
        self.assertIn(
            "5-hour: ●●●●●●○○○○○○ 50% used · budget ${}\x1b[0m | ansi=true".format(
                BUDGETS["deepseek"]["five_hour_cost_usd"]
            ),
            output,
        )
        self.assertIn(
            "1K processed tokens · 200 uncached tokens · 3 calls · $0.50 · local activity",
            output,
        )

    def test_renders_extension_owned_activity_metrics(self):
        extension = ProviderExtension(
            id="fixture",
            name="Fixture Provider",
            auth_type="api-key",
            account_type="api",
            quota_type="activity",
            collect=lambda: ProviderResult(name="Fixture Provider"),
            activity=ActivityExtension(
                budget_info=lambda _a: LocalBudgetInfo(40, "budget $1"),
                detail_lines=lambda _a: ["0.4 units"],
            ),
        )
        output = show(
            [
                ProviderResult(
                    extension_id="fixture",
                    name="Fixture Provider",
                    activity=[ActivityWindow("Weekly", 1_000, 200, 2, cost=0.4)],
                )
            ],
            extensions=[extension],
        )
        self.assertIn("\x1b[32mWeekly:", output)
        self.assertIn("Weekly: ●●●●●○○○○○○○ 40% used · budget $1", output)
        self.assertIn("0.4 units · local activity\x1b[0m | ansi=true", output)


class DetailTest(unittest.TestCase):
    def test_renders_balances_in_purple(self):
        output = show(
            [
                ProviderResult(
                    name="DeepSeek",
                    details=[DetailLine("12.34 USD available", ansi_color=35)],
                )
            ]
        )
        self.assertIn("\x1b[35m12.34 USD available\x1b[0m | ansi=true", output)

    def test_renders_errors_with_a_warning_glyph(self):
        output = show([ProviderResult(name="Kimi Code", error="logged out")])
        self.assertIn("\x1b[31m⚠ logged out\x1b[0m | ansi=true", output)


def _index(lines, needle):
    return next(index for index, line in enumerate(lines) if needle in line)


class UsageColorTest(unittest.TestCase):
    def test_a_failed_provider_is_red_even_when_it_reports_activity(self):
        # DeepSeek returns local activity on an HTTP error, and its budget
        # reads 0% with no spend, which used to paint the menu bar green.
        extension = next(e for e in EXTENSIONS if e.id == "deepseek")
        result = ProviderResult(
            name="DeepSeek",
            extension_id="deepseek",
            error="HTTP 503",
            activity=[ActivityWindow(label="Weekly"), ActivityWindow(label="5-hour")],
        )

        self.assertIn("\x1b[31m", Icon(Usage(extension, result)))


if __name__ == "__main__":
    unittest.main()
