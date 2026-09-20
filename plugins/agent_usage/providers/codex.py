"""Codex quotas, plus a credit estimate from local Codex and Pi sessions."""

from __future__ import annotations

import calendar
import math
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from swiftbar.jsonl_cache import JsonlCache

from ..config import CACHE_DIR, HOME, MENU_COLORS
from ..pricing.codex import (
    CODEX_CREDITS_PER_USD,
    CODEX_FALLBACK_MODEL,
    codex_credits,
    pricing_cache_version,
)
from ..sources.pi import PiUsageEvent, collect_pi_usage_events, parse_pi_usage_event
from ..types import (
    ActivityExtension,
    ActivityWindow,
    DetailLine,
    LocalBudgetInfo,
    LocalUsageEvent,
    Meter,
    ProviderExtension,
    ProviderResult,
    RollingLocalUsage,
)
from ..usage import (
    MonthlyCycle,
    accumulate_rolling_usage,
    empty_rolling_local_usage,
    merge_rolling_usage,
    monthly_activity_windows,
)
from ..utils import (
    MS_PER_DAY,
    clamp_percent,
    clean_error,
    compact_number,
    fetch_json,
    now_ms,
    number_at,
    number_value,
    object_at,
    parse_date,
    read_json,
    reset_from_window,
    string_at,
    to_ms,
)

AVERAGE_WEEKS_PER_MONTH = 365.2425 / 7 / 12
CODEX_MONTHLY_CREDITS = 20_000
USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
DASHBOARD = "https://chatgpt.com/codex/settings/usage"

# Warning budgets for local activity when the service does not report a
# comparable quota percentage. These are estimates, not provider limits.
CODEX_ACTIVITY_BUDGET = {
    "monthly_credits": CODEX_MONTHLY_CREDITS,
    # Derive the rolling seven-day warning from the monthly target.
    "weekly_credits": round(CODEX_MONTHLY_CREDITS / AVERAGE_WEEKS_PER_MONTH),
    "five_hour_credits": 125,
}


@dataclass
class CodexOptions:
    #: UTC calendar day on which the monthly usage cycle resets.
    monthly_cycle_day: int | None = None


def create_codex_extension(
    options: CodexOptions | None = None, monthly_cycle_day: int | None = None
) -> ProviderExtension:
    resolved = options or CodexOptions(monthly_cycle_day=monthly_cycle_day)

    return ProviderExtension(
        id="codex",
        name="Codex",
        auth_type="oauth",
        account_type="hybrid",
        quota_type="hybrid",
        collect=lambda: fetch_codex(resolved),
        activity=CODEX_ACTIVITY_EXTENSION,
    )


def parse_codex_usage(body: dict, headers: dict | None = None) -> list[Meter]:
    headers = headers or {}
    meters: list[Meter] = []
    spend_limit = object_at(object_at(body, "spend_control"), "individual_limit")
    limit = number_at(spend_limit, "limit")
    used = number_at(spend_limit, "used")
    used_percent = number_at(spend_limit, "used_percent")

    if used_percent is None and limit and limit > 0 and used is not None:
        used_percent = used / limit * 100

    if limit is not None and limit > 0 and used_percent is not None:
        meters.append(
            Meter(
                label="Monthly",
                used_percent=clamp_percent(used_percent),
                resets_at=reset_from_window(spend_limit),
                detail=(
                    f"limit {compact_number(limit)} credits"
                    if used is None
                    else f"{compact_number(max(0.0, used))}/"
                    f"{compact_number(limit)} credits"
                ),
            )
        )

    rate_limit = object_at(body, "rate_limit")
    primary = object_at(rate_limit, "primary_window")
    secondary = object_at(rate_limit, "secondary_window")
    primary_used = _header_percent(headers, "x-codex-primary-used-percent")

    if primary_used is None:
        primary_used = number_at(primary, "used_percent")

    secondary_used = _header_percent(headers, "x-codex-secondary-used-percent")

    if secondary_used is None:
        secondary_used = number_at(secondary, "used_percent")

    if secondary_used is not None:
        meters.append(
            Meter(
                label="Weekly",
                used_percent=clamp_percent(secondary_used),
                resets_at=reset_from_window(secondary),
            )
        )

    if primary_used is not None:
        meters.append(
            Meter(
                label="5-hour",
                used_percent=clamp_percent(primary_used),
                resets_at=reset_from_window(primary),
            )
        )

    return meters


def _header_percent(headers, name: str) -> float | None:
    getter = getattr(headers, "get", None)

    return number_value(getter(name)) if getter else None


def parse_codex_model(value: Any) -> str | None:
    if not isinstance(value, dict) or value.get("type") != "turn_context":
        return None

    return string_at(object_at(value, "payload"), "model")


def parse_codex_token_event(
    value: Any, model: str = CODEX_FALLBACK_MODEL
) -> LocalUsageEvent | None:
    # Approval-review sidecars are internal Codex bookkeeping, not user tasks.
    if model.lower() == "codex-auto-review":
        return None

    if not isinstance(value, dict) or value.get("type") != "event_msg":
        return None

    payload = object_at(value, "payload")

    if payload is None or payload.get("type") != "token_count":
        return None

    usage = object_at(object_at(payload, "info"), "last_token_usage")
    timestamp = to_ms(parse_date(value.get("timestamp")))
    input_tokens = number_at(usage, "input_tokens")
    cached = number_at(usage, "cached_input_tokens") or 0.0
    output_tokens = number_at(usage, "output_tokens")
    total = number_at(usage, "total_tokens")

    if timestamp is None or input_tokens is None or output_tokens is None:
        return None

    uncached_input = max(0.0, input_tokens - cached)

    return LocalUsageEvent(
        timestamp=timestamp,
        total_tokens=total if total is not None else input_tokens + output_tokens,
        uncached_tokens=uncached_input + output_tokens,
        credits=codex_credits(model, uncached_input, cached, output_tokens),
    )


def parse_pi_codex_token_event(value: Any) -> LocalUsageEvent | None:
    event = parse_pi_usage_event(value)

    return _event_from_pi(event) if event else None


def _event_from_pi(event: PiUsageEvent) -> LocalUsageEvent | None:
    if event.provider != "openai-codex":
        return None

    uncached = max(0.0, event.total_tokens - event.cache_read_tokens) or (
        event.input_tokens + event.output_tokens + event.cache_write_tokens
    )

    return LocalUsageEvent(
        timestamp=event.timestamp,
        total_tokens=event.total_tokens,
        uncached_tokens=uncached,
        credits=codex_credits(
            event.model or CODEX_FALLBACK_MODEL,
            event.input_tokens,
            event.cache_read_tokens,
            event.output_tokens,
            event.cache_write_tokens,
            event.input_tokens + event.cache_read_tokens + event.cache_write_tokens,
        ),
    )


def _session_files(period_start: float) -> list[str]:
    files: list[str] = []
    seen = set()
    now = now_ms()
    days = max(7, math.ceil((now - period_start) / MS_PER_DAY) + 1)

    for offset in range(days + 1):
        moment = datetime.fromtimestamp((now - offset * MS_PER_DAY) / 1000)

        for date in (moment, moment.astimezone(UTC)):
            directory = os.path.join(
                HOME,
                ".codex",
                "sessions",
                f"{date.year:04d}",
                f"{date.month:02d}",
                f"{date.day:02d}",
            )

            if directory in seen:
                continue

            seen.add(directory)

            try:
                names = os.listdir(directory)
            except (FileNotFoundError, NotADirectoryError):
                continue

            files.extend(
                os.path.join(directory, name)
                for name in names
                if name.endswith(".jsonl")
            )

    return files


def _decode_event(value: Any) -> LocalUsageEvent | None:
    if not isinstance(value, dict):
        return None

    try:
        event = LocalUsageEvent(**value)
    except TypeError:
        return None

    numbers = (event.timestamp, event.total_tokens, event.uncached_tokens)

    if not all(isinstance(number, (int, float)) for number in numbers):
        return None

    for optional in (event.credits, event.cost):
        if optional is not None and not isinstance(optional, (int, float)):
            return None

    return event


def _collect_local_usage(now: float, period_start: float) -> RollingLocalUsage:
    native = empty_rolling_local_usage(credits=True)

    def parse(record, state):
        model = parse_codex_model(record) or state.get("model", CODEX_FALLBACK_MODEL)

        return {"model": model}, parse_codex_token_event(record, model)

    cache = JsonlCache(
        cache_path=os.path.join(CACHE_DIR, "codex-sessions.json"),
        version=f"codex-py1-{pricing_cache_version()}",
        now=now,
        retention_ms=max(32 * MS_PER_DAY, now - period_start),
        parse=parse,
        encode_event=asdict,
        decode_event=_decode_event,
        event_timestamp=lambda event: event.timestamp,
        initial_state=lambda: {"model": CODEX_FALLBACK_MODEL},
    )

    for event in cache.events(_session_files(period_start)):
        accumulate_rolling_usage(native, event, now, period_start)

    return merge_rolling_usage(native, _collect_pi_usage(now, period_start))


def _collect_pi_usage(now: float, period_start: float) -> RollingLocalUsage:
    usage = empty_rolling_local_usage(credits=True)

    for pi_event in collect_pi_usage_events():
        event = _event_from_pi(pi_event)

        if event:
            accumulate_rolling_usage(usage, event, now, period_start)

    return usage


def codex_budget_info(activity: ActivityWindow) -> LocalBudgetInfo | None:
    budgets = {
        "Monthly": CODEX_ACTIVITY_BUDGET["monthly_credits"],
        "Rolling 30-day": CODEX_ACTIVITY_BUDGET["monthly_credits"],
        "Weekly": CODEX_ACTIVITY_BUDGET["weekly_credits"],
        "5-hour": CODEX_ACTIVITY_BUDGET["five_hour_credits"],
    }
    budget = budgets.get(activity.label)

    if budget is None:
        return None

    return LocalBudgetInfo(
        used_percent=(activity.credits or 0.0) / budget * 100,
        detail=(
            f"budget {compact_number(budget)} credits"
            f" ≈ ${budget / CODEX_CREDITS_PER_USD:.0f}"
        ),
    )


def codex_activity_details(activity: ActivityWindow) -> list[str]:
    if activity.credits is None:
        return []

    return [
        f"{compact_number(activity.credits)} credits"
        f" ≈ ${activity.credits / CODEX_CREDITS_PER_USD:.2f}"
    ]


CODEX_ACTIVITY_EXTENSION = ActivityExtension(
    budget_info=codex_budget_info, detail_lines=codex_activity_details
)


def codex_activity_windows(
    usage: RollingLocalUsage, cycle: MonthlyCycle | None = None
) -> list[ActivityWindow]:
    return monthly_activity_windows(usage, cycle)


def monthly_cycle_window(cycle_day: int, now: float | None = None) -> MonthlyCycle:
    if (
        not isinstance(cycle_day, int)
        or isinstance(cycle_day, bool)
        or not 1 <= cycle_day <= 31
    ):
        raise ValueError(f"Invalid Codex monthly cycle day: {cycle_day}")

    now = now_ms() if now is None else now
    current = datetime.fromtimestamp(now / 1000, UTC)
    start = _occurrence(current.year, current.month, cycle_day)

    if to_ms(start) > now:
        start = _occurrence(
            *_previous_month(current.year, current.month), day=cycle_day
        )

    resets_at = _occurrence(*_next_month(start.year, start.month), day=cycle_day)

    return MonthlyCycle(started_at=to_ms(start), resets_at=resets_at)


def monthly_cycle_from_reset(resets_at: datetime) -> MonthlyCycle:
    resets_at = resets_at.astimezone(UTC)
    year, month = _previous_month(resets_at.year, resets_at.month)
    last_day = calendar.monthrange(year, month)[1]
    started_at = resets_at.replace(
        year=year, month=month, day=min(resets_at.day, last_day)
    )

    return MonthlyCycle(started_at=to_ms(started_at), resets_at=resets_at)


def _occurrence(year: int, month: int, day: int) -> datetime:
    last_day = calendar.monthrange(year, month)[1]

    return datetime(year, month, min(day, last_day), tzinfo=UTC)


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def fetch_codex(options: CodexOptions | None = None) -> ProviderResult:
    options = options or CodexOptions()
    auth = read_json(os.path.join(HOME, ".codex", "auth.json"))
    tokens = object_at(auth, "tokens")
    access_token = string_at(tokens, "access_token")
    account_id = string_at(tokens, "account_id")

    if not access_token:
        return ProviderResult(name="Codex", error="Not logged in; run codex login")

    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": "agent-usage-swiftbar",
        }

        if account_id:
            headers["ChatGPT-Account-Id"] = account_id

        body, response_headers = fetch_json(USAGE_URL, headers)
        meters = parse_codex_usage(body, response_headers)
        plan_type = string_at(body, "plan_type")
        subtitle = plan_type.upper() if plan_type else None
        unlimited = (object_at(body, "credits") or {}).get("unlimited") is True
        now = now_ms()
        reported_reset = next(
            (m.resets_at for m in meters if m.label == "Monthly"), None
        )

        if reported_reset:
            cycle = monthly_cycle_from_reset(reported_reset)
        elif options.monthly_cycle_day:
            cycle = monthly_cycle_window(options.monthly_cycle_day, now)
        else:
            cycle = None

        period_start = cycle.started_at if cycle else now - 30 * MS_PER_DAY
        activity = codex_activity_windows(
            _collect_local_usage(now, period_start), cycle
        )

        if not meters and unlimited:
            return ProviderResult(
                name="Codex",
                subtitle=subtitle,
                activity=activity,
                details=[
                    DetailLine(
                        text="Unlimited · no server-side rate-limit windows · "
                        "Codex + Pi activity",
                        ansi_color=MENU_COLORS["accent"],
                        font="Menlo",
                    )
                ],
                dashboard=DASHBOARD,
            )

        if not meters:
            return ProviderResult(name="Codex", error="No quota windows returned")

        return ProviderResult(
            name="Codex",
            meters=meters,
            subtitle=subtitle,
            activity=activity,
            dashboard=DASHBOARD,
        )
    except Exception as error:  # noqa: BLE001 - surfaced as a menu row
        return ProviderResult(name="Codex", error=clean_error(error))
