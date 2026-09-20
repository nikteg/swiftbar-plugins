"""Kimi Code subscription quotas, plus local activity from Pi sessions."""

from __future__ import annotations

import os
from typing import Any

from swiftbar_lib.state import write_json

from ..config import HOME
from ..sources.pi import PiUsageEvent, collect_pi_usage_events, parse_pi_usage_event
from ..types import (
    LocalUsageEvent,
    Meter,
    ProviderExtension,
    ProviderResult,
    RollingLocalUsage,
)
from ..usage import (
    accumulate_rolling_usage,
    empty_rolling_local_usage,
    local_activity_windows,
)
from ..utils import (
    clamp_percent,
    clean_error,
    fetch_json,
    now_ms,
    number_at,
    object_at,
    parse_date,
    post_json,
    read_json,
    string_at,
)

KIMI_CLIENT_ID = "17e5f671-d194-4dfb-9706-5516cb48c098"
USAGE_URL = "https://api.kimi.com/coding/v1/usages"
TOKEN_URL = "https://auth.kimi.com/api/oauth/token"
DASHBOARD = "https://www.kimi.com/code/console"
LOGIN_HINT = "Kimi login expired; use pi /login kimi-coding"

KIMI_MEMBERSHIPS = {
    "LEVEL_FREE": "Adagio",
    "LEVEL_BASIC": "Moderato",
    "LEVEL_STANDARD": "Allegretto",
    "LEVEL_INTERMEDIATE": "Allegro",
    "LEVEL_ADVANCED": "Vivace",
    "LEVEL_PREMIUM": "Vivace",
}


def create_kimi_extension() -> ProviderExtension:
    return ProviderExtension(
        id="kimi-code",
        name="Kimi Code",
        auth_type="oauth",
        account_type="subscription",
        quota_type="reported",
        collect=fetch_kimi,
    )


def parse_kimi_membership(body: dict) -> str | None:
    membership = object_at(object_at(body, "user"), "membership")
    display_name = (
        string_at(membership, "display_name")
        or string_at(membership, "name")
        or string_at(membership, "title")
    )

    if display_name:
        return display_name

    code = string_at(membership, "level")

    return KIMI_MEMBERSHIPS.get(code, code) if code else None


def _kimi_row(label: str, source: Any) -> Meter | None:
    if not isinstance(source, dict):
        return None

    limit = number_at(source, "limit")
    used = number_at(source, "used")
    remaining = number_at(source, "remaining")

    if used is None and limit is not None and remaining is not None:
        used = limit - remaining

    if used is None or limit is None or limit <= 0:
        return None

    reset = source.get("resetTime", source.get("reset_time", source.get("resets_at")))

    return Meter(
        label=label,
        used_percent=clamp_percent(used / limit * 100),
        resets_at=parse_date(reset),
        detail=f"{max(0.0, used):g}/{limit:g} requests",
    )


def parse_kimi_usage(body: dict) -> list[Meter]:
    meters = []
    weekly = _kimi_row("Weekly", body.get("usage"))

    if weekly:
        meters.append(weekly)

    limits = body.get("limits")

    for index, value in enumerate(limits if isinstance(limits, list) else []):
        if not isinstance(value, dict):
            continue

        window = object_at(value, "window")
        duration = number_at(window, "duration")
        unit = string_at(window, "timeUnit") or string_at(window, "time_unit")
        minutes = (duration or 0) * 60 if unit and "HOUR" in unit.upper() else duration
        label = (
            f"{minutes / 60:g}-hour"
            if minutes and minutes % 60 == 0
            else f"Limit {index + 1}"
        )
        meter = _kimi_row(label, value.get("detail", value))

        if meter:
            meters.append(meter)

    return meters


def _request_usage(access_token: str) -> dict:
    body, _headers = fetch_json(
        USAGE_URL,
        {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": "kimi-code-cli/0.26.0",
            "X-Msh-Platform": "kimi_code_cli",
            "X-Msh-Version": "0.26.0",
        },
    )

    return body


def apply_kimi_token_response(
    kimi: dict, response: dict, now: float | None = None
) -> str:
    now = now_ms() if now is None else now
    access_token = string_at(response, "access_token")
    refresh_token = string_at(response, "refresh_token") or string_at(kimi, "refresh")

    if not access_token or not refresh_token:
        raise RuntimeError("Kimi token refresh returned incomplete credentials")

    kimi["access"] = access_token
    kimi["refresh"] = refresh_token
    kimi["expires"] = now + (number_at(response, "expires_in") or 3600) * 1000

    return access_token


def _refresh_token(auth: dict) -> str:
    kimi = object_at(auth, "kimi-coding")
    refresh_token = string_at(kimi, "refresh")

    if not kimi or not refresh_token:
        raise RuntimeError(LOGIN_HINT)

    try:
        response = post_json(
            TOKEN_URL,
            [
                ("client_id", KIMI_CLIENT_ID),
                ("grant_type", "refresh_token"),
                ("refresh_token", refresh_token),
            ],
        )
    except Exception:  # noqa: BLE001 - any failure means re-login
        raise RuntimeError(LOGIN_HINT) from None

    access_token = apply_kimi_token_response(kimi, response)
    write_json(os.path.join(HOME, ".pi", "agent", "auth.json"), auth, private=True)

    return access_token


def fetch_kimi() -> ProviderResult:
    auth = read_json(os.path.join(HOME, ".pi", "agent", "auth.json"))
    kimi = object_at(auth, "kimi-coding")
    access_token = string_at(kimi, "access")

    if not access_token:
        return ProviderResult(
            name="Kimi Code", error="Not logged in; use pi /login kimi-coding"
        )

    try:
        expires = number_at(kimi, "expires")

        if auth and expires is not None and expires <= now_ms() + 300_000:
            access_token = _refresh_token(auth)

        try:
            body = _request_usage(access_token)
        except Exception as error:  # noqa: BLE001 - one retry after a refresh
            if not auth or clean_error(error) != "HTTP 401":
                raise

            access_token = _refresh_token(auth)
            body = _request_usage(access_token)

        meters = parse_kimi_usage(body)

        if not meters:
            return ProviderResult(name="Kimi Code", error="No quota windows returned")

        return ProviderResult(
            name="Kimi Code",
            meters=meters,
            subtitle=parse_kimi_membership(body),
            activity=local_activity_windows(_collect_local_usage()),
            dashboard=DASHBOARD,
        )
    except Exception as error:  # noqa: BLE001 - surfaced as a menu row
        return ProviderResult(name="Kimi Code", error=clean_error(error))


def parse_kimi_token_event(value: Any) -> LocalUsageEvent | None:
    event = parse_pi_usage_event(value)

    return _event_from_pi(event) if event else None


def _event_from_pi(event: PiUsageEvent) -> LocalUsageEvent | None:
    if event.provider != "kimi-coding":
        return None

    uncached = max(0.0, event.total_tokens - event.cache_read_tokens) or (
        event.input_tokens + event.output_tokens + event.cache_write_tokens
    )

    return LocalUsageEvent(
        timestamp=event.timestamp,
        total_tokens=event.total_tokens,
        uncached_tokens=uncached,
    )


def _collect_local_usage() -> RollingLocalUsage:
    usage = empty_rolling_local_usage()
    now = now_ms()

    for pi_event in collect_pi_usage_events():
        event = _event_from_pi(pi_event)

        if event:
            accumulate_rolling_usage(usage, event, now)

    return usage
