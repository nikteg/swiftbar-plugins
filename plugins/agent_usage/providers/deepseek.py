"""DeepSeek API balance, plus local cost from OpenCode sessions."""

from __future__ import annotations

from typing import Any

from ..config import MENU_COLORS
from ..provider import KeychainSecret, api_key_auth, define_provider, http_json_quota
from ..sources.opencode import (
    OpenCodeUsageEvent,
    collect_opencode_usage_events,
    parse_opencode_usage_event,
)
from ..types import (
    ActivityExtension,
    ActivityWindow,
    DetailLine,
    LocalBudgetInfo,
    LocalUsageEvent,
    ProviderExtension,
    ProviderResult,
    RollingLocalUsage,
)
from ..usage import (
    accumulate_rolling_usage,
    empty_rolling_local_usage,
    local_activity_windows,
)
from ..utils import now_ms, string_at

BALANCE_URL = "https://api.deepseek.com/user/balance"
DASHBOARD = "https://platform.deepseek.com/usage"
KEYCHAIN_SERVICE = "deepseek-api-key"

DEEPSEEK_ACTIVITY_BUDGET = {"five_hour_cost_usd": 1, "weekly_cost_usd": 5}


def parse_deepseek_balance(body: dict) -> list[str]:
    balances = body.get("balance_infos")
    lines = []

    for value in balances if isinstance(balances, list) else []:
        amount = string_at(value, "total_balance")
        currency = string_at(value, "currency")

        if amount and currency:
            lines.append(f"{amount} {currency} available")

    return lines


def deepseek_budget_info(activity: ActivityWindow) -> LocalBudgetInfo | None:
    budgets = {
        "Weekly": DEEPSEEK_ACTIVITY_BUDGET["weekly_cost_usd"],
        "5-hour": DEEPSEEK_ACTIVITY_BUDGET["five_hour_cost_usd"],
    }
    budget = budgets.get(activity.label)

    if budget is None:
        return None

    return LocalBudgetInfo(
        used_percent=(activity.cost or 0.0) / budget * 100,
        detail=f"budget ${budget}",
    )


def deepseek_activity_details(activity: ActivityWindow) -> list[str]:
    if activity.cost is None:
        return []

    return ["${:.{}f}".format(activity.cost, 4 if activity.cost < 0.01 else 2)]


DEEPSEEK_ACTIVITY_EXTENSION = ActivityExtension(
    budget_info=deepseek_budget_info, detail_lines=deepseek_activity_details
)


def _activity() -> list[ActivityWindow]:
    return local_activity_windows(_collect_local_usage())


def _parse_balance(body: dict, _headers) -> ProviderResult:
    balances = parse_deepseek_balance(body)

    if not balances:
        raise RuntimeError("No balance returned")

    return ProviderResult(
        name="",
        activity=_activity(),
        details=[
            DetailLine(text=text, ansi_color=MENU_COLORS["accent"], font="Menlo")
            for text in balances
        ],
        lines=(
            ["Balance unavailable for API calls"]
            if body.get("is_available") is False
            else []
        ),
        dashboard=DASHBOARD,
    )


def create_deepseek_extension(secret: Any = None) -> ProviderExtension:
    """`secret` is any provider secret source; defaults to the login Keychain."""
    return define_provider(
        id="deepseek",
        name="DeepSeek",
        account_type="api",
        auth=api_key_auth(
            source=secret or KeychainSecret(KEYCHAIN_SERVICE),
            scheme="Bearer",
            missing_message=(
                "No API key configured"
                if secret
                else f"No API key in Keychain item {KEYCHAIN_SERVICE}"
            ),
        ),
        quota=http_json_quota(
            type="activity",
            url=BALANCE_URL,
            headers={"Accept": "application/json"},
            parse=_parse_balance,
            on_error=lambda _error: ProviderResult(name="", activity=_activity()),
        ),
        activity=DEEPSEEK_ACTIVITY_EXTENSION,
    )


def parse_deepseek_token_event(value: Any) -> LocalUsageEvent | None:
    event = parse_opencode_usage_event(value)

    return _event_from_opencode(event) if event else None


def _event_from_opencode(event: OpenCodeUsageEvent) -> LocalUsageEvent | None:
    if event.provider != "deepseek":
        return None

    return LocalUsageEvent(
        timestamp=event.timestamp,
        total_tokens=event.total_tokens,
        uncached_tokens=max(0.0, event.total_tokens - event.cache_read_tokens),
        cost=event.cost,
    )


def _collect_local_usage() -> RollingLocalUsage:
    usage = empty_rolling_local_usage(cost=True)
    now = now_ms()

    for opencode_event in collect_opencode_usage_events():
        event = _event_from_opencode(opencode_event)

        if event:
            accumulate_rolling_usage(usage, event, now)

    return usage
