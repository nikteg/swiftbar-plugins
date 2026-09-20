import unittest
from datetime import UTC, datetime

from agent_usage.providers.claude import (
    apply_claude_token_response,
    parse_claude_usage,
    should_refresh_claude_token,
)
from agent_usage.providers.codex import (
    codex_activity_windows,
    monthly_cycle_from_reset,
    monthly_cycle_window,
    parse_codex_token_event,
    parse_codex_usage,
    parse_pi_codex_token_event,
)
from agent_usage.providers.deepseek import (
    parse_deepseek_balance,
    parse_deepseek_token_event,
)
from agent_usage.providers.kimi import (
    apply_kimi_token_response,
    parse_kimi_membership,
    parse_kimi_token_event,
    parse_kimi_usage,
)
from agent_usage.sources.claude import parse_claude_usage_event
from agent_usage.sources.pi import parse_pi_usage_event
from agent_usage.types import LocalUsageEvent
from agent_usage.usage import accumulate_rolling_usage, empty_rolling_local_usage

EPOCH_2030 = 1_893_456_000_000  # 2030-01-01T00:00:00Z


def ms(text: str) -> float:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000


def _event(timestamp: float, credits: float) -> LocalUsageEvent:
    return LocalUsageEvent(
        timestamp=timestamp,
        total_tokens=credits,
        uncached_tokens=credits,
        credits=credits,
    )


class ClaudeTest(unittest.TestCase):
    def test_parses_utilization(self):
        meters = parse_claude_usage(
            {
                "five_hour": {"utilization": 34, "resets_at": "2030-01-01T00:00:00Z"},
                "seven_day": {"utilization": 61, "resets_at": "2030-01-07T00:00:00Z"},
            }
        )
        self.assertEqual(
            [(m.label, m.used_percent) for m in meters],
            [("Weekly", 61), ("5-hour", 34)],
        )

    def test_adds_scoped_weekly_limits_once(self):
        meters = parse_claude_usage(
            {
                "seven_day_opus": {"utilization": 10},
                "limits": [
                    {
                        "kind": "weekly_scoped",
                        "display_name": "Opus",
                        "utilization": 10,
                    },
                    {"kind": "weekly_scoped", "scope": "Haiku", "utilization": 5},
                ],
            }
        )
        self.assertEqual([m.label for m in meters], ["Opus weekly", "Haiku"])

    def test_parses_local_token_usage(self):
        event = parse_claude_usage_event(
            {
                "type": "assistant",
                "requestId": "request-1",
                "timestamp": "2030-01-01T00:00:00Z",
                "message": {
                    "model": "claude-opus-5",
                    "stop_reason": "end_turn",
                    "usage": {
                        "input_tokens": 10,
                        "cache_creation_input_tokens": 30,
                        "cache_read_input_tokens": 50,
                        "output_tokens": 20,
                    },
                },
            }
        )
        self.assertEqual(
            (
                event.event_id,
                event.timestamp,
                event.total_tokens,
                event.uncached_tokens,
            ),
            ("request-1", EPOCH_2030, 110, 60),
        )

    def test_ignores_partial_streaming_snapshots(self):
        self.assertIsNone(
            parse_claude_usage_event(
                {
                    "type": "assistant",
                    "requestId": "request-1",
                    "timestamp": "2030-01-01T00:00:00Z",
                    "message": {
                        "model": "claude-opus-5",
                        "stop_reason": None,
                        "usage": {"input_tokens": 10, "output_tokens": 1},
                    },
                }
            )
        )

    def test_keeps_refresh_token_when_response_omits_it(self):
        oauth = {"refreshToken": "existing-refresh"}
        access = apply_claude_token_response(
            oauth, {"access_token": "new-access", "expires_in": 1800}, 1_000
        )
        self.assertEqual(access, "new-access")
        self.assertEqual(
            oauth,
            {
                "refreshToken": "existing-refresh",
                "accessToken": "new-access",
                "expiresAt": 1_801_000,
            },
        )

    def test_stores_rotated_refresh_token(self):
        oauth = {"refreshToken": "old-refresh"}
        apply_claude_token_response(
            oauth,
            {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            },
            2_000,
        )
        self.assertEqual(oauth["refreshToken"], "new-refresh")

    def test_rejects_incomplete_refresh_response(self):
        with self.assertRaises(RuntimeError):
            apply_claude_token_response({}, {"expires_in": 60})

    def test_refreshes_with_two_swiftbar_cycles_of_margin(self):
        now = EPOCH_2030
        self.assertTrue(should_refresh_claude_token(now + 30 * 60_000, now))
        self.assertFalse(should_refresh_claude_token(now + 30 * 60_000 + 1, now))


class CodexTest(unittest.TestCase):
    def test_parses_rate_limit_windows(self):
        meters = parse_codex_usage(
            {
                "rate_limit": {
                    "primary_window": {"used_percent": 12, "reset_after_seconds": 100},
                    "secondary_window": {"used_percent": 45, "reset_at": 2_000_000_000},
                }
            }
        )
        self.assertEqual(
            [(m.label, m.used_percent) for m in meters],
            [("Weekly", 45), ("5-hour", 12)],
        )

    def test_parses_api_level_monthly_spend_limit(self):
        meters = parse_codex_usage(
            {
                "rate_limit": None,
                "spend_control": {
                    "individual_limit": {
                        "limit": "20000",
                        "used": "4693.449445486069",
                        "used_percent": 23,
                        "reset_at": 1_788_220_800,
                    }
                },
            }
        )
        self.assertEqual(len(meters), 1)
        self.assertEqual(
            (meters[0].label, meters[0].used_percent, meters[0].detail),
            ("Monthly", 23, "4.7K/20K credits"),
        )
        self.assertEqual(meters[0].resets_at.isoformat(), "2026-09-01T00:00:00+00:00")

    def test_derives_usage_percent_when_omitted(self):
        meters = parse_codex_usage(
            {"spend_control": {"individual_limit": {"limit": "20000", "used": "5000"}}}
        )
        self.assertEqual(
            (meters[0].label, meters[0].used_percent, meters[0].detail),
            ("Monthly", 25, "5K/20K credits"),
        )

    def test_prefers_percent_headers_over_the_body(self):
        meters = parse_codex_usage(
            {"rate_limit": {"primary_window": {"used_percent": 12}}},
            {"x-codex-primary-used-percent": "77"},
        )
        self.assertEqual(meters[0].used_percent, 77)

    def test_parses_local_token_events(self):
        event = parse_codex_token_event(
            {
                "timestamp": "2030-01-01T00:00:00Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {
                            "input_tokens": 10_000,
                            "cached_input_tokens": 8_000,
                            "output_tokens": 500,
                            "total_tokens": 10_500,
                        }
                    },
                },
            },
            "gpt-5.6-luna",
        )
        self.assertEqual((event.total_tokens, event.uncached_tokens), (10_500, 2_500))
        self.assertAlmostEqual(event.credits, 0.029)

    def test_ignores_internal_approval_review_activity(self):
        self.assertIsNone(
            parse_codex_token_event(
                {
                    "type": "event_msg",
                    "timestamp": "2030-01-01T00:00:00Z",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "last_token_usage": {
                                "input_tokens": 10_000,
                                "cached_input_tokens": 8_000,
                                "output_tokens": 500,
                                "total_tokens": 10_500,
                            }
                        },
                    },
                },
                "codex-auto-review",
            )
        )

    def test_parses_pi_codex_token_events(self):
        event = parse_pi_codex_token_event(
            {
                "timestamp": "2030-01-01T00:00:00Z",
                "type": "message",
                "message": {
                    "role": "assistant",
                    "provider": "openai-codex",
                    "model": "gpt-5.6-luna",
                    "usage": {
                        "input": 4_536,
                        "output": 67,
                        "cacheRead": 4_608,
                        "cacheWrite": 0,
                        "totalTokens": 9_211,
                        "cost": {"total": 0.0053988},
                    },
                },
            }
        )
        self.assertEqual((event.total_tokens, event.uncached_tokens), (9_211, 4_603))
        self.assertAlmostEqual(event.credits, 0.026994)
        self.assertIsNone(event.cost)

    def test_ignores_other_providers_in_pi_sessions(self):
        self.assertIsNone(
            parse_pi_codex_token_event(
                {
                    "timestamp": "2030-01-01T00:00:00Z",
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "provider": "deepseek",
                        "usage": {"totalTokens": 5},
                    },
                }
            )
        )

    def test_uses_rolling_thirty_days_without_a_monthly_reset(self):
        windows = codex_activity_windows(empty_rolling_local_usage(credits=True))
        self.assertEqual(
            [window.label for window in windows],
            ["Rolling 30-day", "Weekly", "5-hour"],
        )

    def test_derives_the_cycle_from_the_reported_reset(self):
        resets_at = datetime(2030, 3, 31, 14, 30, tzinfo=UTC)
        cycle = monthly_cycle_from_reset(resets_at)
        self.assertEqual(
            datetime.fromtimestamp(cycle.started_at / 1000, UTC).isoformat(),
            "2030-02-28T14:30:00+00:00",
        )
        window = codex_activity_windows(empty_rolling_local_usage(credits=True), cycle)[
            0
        ]
        self.assertEqual((window.label, window.resets_at), ("Monthly", resets_at))

    def test_tracks_activity_from_a_configured_monthly_cycle(self):
        usage = empty_rolling_local_usage(credits=True)
        now = ms("2030-09-01T00:00:00Z")
        cycle = monthly_cycle_window(10, now)
        self.assertEqual(
            datetime.fromtimestamp(cycle.started_at / 1000, UTC).isoformat(),
            "2030-08-10T00:00:00+00:00",
        )
        self.assertEqual(cycle.resets_at.isoformat(), "2030-09-10T00:00:00+00:00")

        for timestamp, credits in (
            ("2030-08-09T23:59:59Z", 10),
            ("2030-08-10T00:00:00Z", 20),
        ):
            accumulate_rolling_usage(
                usage,
                _event(ms(timestamp), credits=credits),
                now,
                cycle.started_at,
            )

        self.assertEqual(usage.period.credits, 20)

    def test_rejects_an_invalid_cycle_day(self):
        with self.assertRaises(ValueError):
            monthly_cycle_window(0)

    def test_tracks_rolling_monthly_and_weekly_activity(self):
        usage = empty_rolling_local_usage(credits=True)
        now = ms("2030-01-31T00:00:00Z")
        accumulate_rolling_usage(usage, _event(ms("2030-01-17T00:00:00Z"), 10), now)
        accumulate_rolling_usage(usage, _event(ms("2030-01-30T00:00:00Z"), 20), now)
        self.assertEqual(usage.period.credits, 30)
        self.assertEqual(usage.seven_day.credits, 20)
        self.assertEqual(usage.five_hour.credits, 0)


class KimiTest(unittest.TestCase):
    def test_parses_request_quotas(self):
        meters = parse_kimi_usage(
            {
                "usage": {
                    "used": "100",
                    "limit": "2048",
                    "resetTime": "2030-01-01T00:00:00Z",
                },
                "limits": [
                    {
                        "window": {"duration": 300, "timeUnit": "TIME_UNIT_MINUTE"},
                        "detail": {
                            "remaining": "150",
                            "limit": "200",
                            "resetTime": "2030-01-01T00:00:00Z",
                        },
                    }
                ],
            }
        )
        self.assertEqual(
            [(m.label, m.detail) for m in meters],
            [("Weekly", "100/2048 requests"), ("5-hour", "50/200 requests")],
        )

    def test_maps_level_basic_to_moderato(self):
        self.assertEqual(
            parse_kimi_membership({"user": {"membership": {"level": "LEVEL_BASIC"}}}),
            "Moderato",
        )

    def test_prefers_a_display_name(self):
        self.assertEqual(
            parse_kimi_membership(
                {
                    "user": {
                        "membership": {"level": "LEVEL_BASIC", "display_name": "Pro"}
                    }
                }
            ),
            "Pro",
        )

    def test_parses_local_token_usage(self):
        event = parse_kimi_token_event(
            {
                "type": "message",
                "timestamp": "2030-01-01T00:00:00Z",
                "message": {
                    "role": "assistant",
                    "provider": "kimi-coding",
                    "usage": {
                        "input": 10,
                        "output": 20,
                        "cacheRead": 50,
                        "cacheWrite": 30,
                        "totalTokens": 110,
                    },
                },
            }
        )
        self.assertEqual(
            (event.timestamp, event.total_tokens, event.uncached_tokens),
            (EPOCH_2030, 110, 60),
        )

    def test_keeps_refresh_token_when_response_omits_it(self):
        kimi = {"refresh": "existing-refresh"}
        access = apply_kimi_token_response(
            kimi, {"access_token": "new-access", "expires_in": 1800}, 1_000
        )
        self.assertEqual(access, "new-access")
        self.assertEqual(
            kimi,
            {
                "refresh": "existing-refresh",
                "access": "new-access",
                "expires": 1_801_000,
            },
        )

    def test_stores_rotated_refresh_token(self):
        kimi = {"refresh": "old-refresh"}
        apply_kimi_token_response(
            kimi,
            {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            },
            2_000,
        )
        self.assertEqual(kimi["refresh"], "new-refresh")


class DeepSeekTest(unittest.TestCase):
    def test_parses_balances(self):
        self.assertEqual(
            parse_deepseek_balance(
                {"balance_infos": [{"currency": "USD", "total_balance": "12.34"}]}
            ),
            ["12.34 USD available"],
        )

    def test_ignores_incomplete_balances(self):
        self.assertEqual(
            parse_deepseek_balance({"balance_infos": [{"currency": "USD"}]}), []
        )

    def test_parses_pi_token_events(self):
        event = parse_deepseek_token_event(
            {
                "timestamp": "2030-01-01T00:00:00Z",
                "type": "message",
                "message": {
                    "role": "assistant",
                    "provider": "deepseek",
                    "usage": {
                        "input": 66,
                        "output": 93,
                        "cacheRead": 293_504,
                        "cacheWrite": 0,
                        "totalTokens": 293_663,
                        "cost": {"total": 0.001173572},
                    },
                },
            }
        )
        self.assertEqual((event.total_tokens, event.uncached_tokens), (293_663, 159))
        self.assertAlmostEqual(event.cost, 0.001173572)


class PiSourceTest(unittest.TestCase):
    def test_keeps_session_parsing_provider_neutral(self):
        event = parse_pi_usage_event(
            {
                "timestamp": "2030-01-01T00:00:00Z",
                "type": "message",
                "message": {
                    "role": "assistant",
                    "provider": "future-provider",
                    "model": "future-model",
                    "usage": {
                        "input": 12,
                        "output": 3,
                        "cacheRead": 4,
                        "cacheWrite": 2,
                        "totalTokens": 21,
                        "cost": {"total": 0.25},
                    },
                },
            }
        )
        self.assertEqual(
            (
                event.timestamp,
                event.provider,
                event.model,
                event.input_tokens,
                event.output_tokens,
                event.cache_read_tokens,
                event.cache_write_tokens,
                event.total_tokens,
                event.cost,
            ),
            (EPOCH_2030, "future-provider", "future-model", 12, 3, 4, 2, 21, 0.25),
        )

    def test_ignores_non_assistant_records(self):
        self.assertIsNone(
            parse_pi_usage_event(
                {"type": "message", "message": {"role": "user", "provider": "x"}}
            )
        )


if __name__ == "__main__":
    unittest.main()
