"""Claude Code subscription quotas, plus local transcript activity."""

from __future__ import annotations

import binascii
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass

from swiftbar_lib.state import write_json

from ..config import HOME, KEYCHAIN_ACCOUNT
from ..sources.claude import claude_desktop_session_ids, collect_claude_usage_events
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
    MS_PER_MINUTE,
    clean_error,
    fetch_json,
    now_ms,
    number_at,
    object_at,
    post_json,
    read_json,
    string_at,
    usage_meter,
)

CLAUDE_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
TOKEN_REFRESH_MARGIN_MS = 30 * MS_PER_MINUTE
DEFAULT_SCOPES = "user:profile user:inference user:sessions:claude_code"
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
DASHBOARD = "https://claude.ai/settings/usage"


@dataclass
class ClaudeProfile:
    name: str
    config_dir: str
    is_default: bool = True
    login_hint: str = "run claude auth login"
    #: Claude Desktop data directory when it launches sessions for this profile.
    desktop_data_dir: str | None = None


DEFAULT_CLAUDE_PROFILE = ClaudeProfile(
    name="Claude Code",
    config_dir=os.path.join(HOME, ".claude"),
    is_default=True,
    login_hint="run claude auth login",
    desktop_data_dir=os.path.join(HOME, "Library/Application Support/Claude"),
)

_registered_profiles: list[ClaudeProfile] = []


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "claude"


def create_claude_extension(
    profile: ClaudeProfile | None = None, id: str | None = None
) -> ProviderExtension:
    """One Claude profile. Defaults to ``~/.claude``; pass a profile for others.

    The id defaults to a slug of the profile name, which only has to be unique
    across the profiles a single plugin file composes.
    """
    profile = profile or DEFAULT_CLAUDE_PROFILE
    _registered_profiles.append(profile)

    return ProviderExtension(
        id=id or _slug(profile.name),
        name=profile.name,
        auth_type="oauth",
        account_type="subscription",
        quota_type="reported",
        collect=lambda: fetch_claude(profile),
    )


def profile_suffix(profile: ClaudeProfile) -> str:
    return hashlib.sha256(profile.config_dir.encode()).hexdigest()[:8]


def _keychain_service(profile: ClaudeProfile) -> str:
    if profile.is_default:
        return "Claude Code-credentials"

    return f"Claude Code-credentials-{profile_suffix(profile)}"


def _find_keychain_item(profile: ClaudeProfile) -> subprocess.CompletedProcess:
    """Look the item up by account first: several Claude Code processes can
    store items under the same service name (one wrote an ``unknown`` account
    holding only MCP tokens), and ``security`` returns the first match."""
    service = _keychain_service(profile)

    for account in (KEYCHAIN_ACCOUNT, None):
        command = ["/usr/bin/security", "find-generic-password"]

        if account is not None:
            command += ["-a", account]

        completed = subprocess.run(
            [*command, "-s", service, "-w"], capture_output=True, timeout=10
        )

        if completed.returncode == 0:
            return completed

    return completed


def _credentials(profile: ClaudeProfile) -> dict | None:
    stored = read_json(os.path.join(profile.config_dir, ".credentials.json"))

    if object_at(stored, "claudeAiOauth"):
        return stored

    try:
        completed = _find_keychain_item(profile)

        if completed.returncode != 0:
            return None

        value = json.loads(completed.stdout.decode())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None

    return value if isinstance(value, dict) else None


def _persist_credentials(credentials: dict, profile: ClaudeProfile) -> None:
    path = os.path.join(profile.config_dir, ".credentials.json")

    if os.path.exists(path):
        # Atomic: a crash mid-write would otherwise leave the file truncated
        # and log this profile out.
        write_json(path, credentials, private=True)

        return

    encoded = binascii.hexlify(json.dumps(credentials).encode()).decode()
    completed = subprocess.run(
        [
            "/usr/bin/security",
            "add-generic-password",
            "-U",
            "-a",
            KEYCHAIN_ACCOUNT,
            "-s",
            _keychain_service(profile),
            "-X",
            encoded,
        ],
        capture_output=True,
    )

    if completed.returncode != 0:
        raise RuntimeError("could not update Claude Code Keychain token")


def should_refresh_claude_token(expires_at: float, now: float | None = None) -> bool:
    now = now_ms() if now is None else now

    return expires_at <= now + TOKEN_REFRESH_MARGIN_MS


def apply_claude_token_response(
    oauth: dict, response: dict, now: float | None = None
) -> str:
    now = now_ms() if now is None else now
    access_token = string_at(response, "access_token")
    refresh_token = string_at(response, "refresh_token") or string_at(
        oauth, "refreshToken"
    )

    if not access_token or not refresh_token:
        raise RuntimeError("Claude token refresh returned incomplete credentials")

    oauth["accessToken"] = access_token
    oauth["refreshToken"] = refresh_token
    oauth["expiresAt"] = now + (number_at(response, "expires_in") or 3600) * 1000

    return access_token


def _refresh_token(credentials: dict, profile: ClaudeProfile) -> str:
    oauth = object_at(credentials, "claudeAiOauth")
    refresh_token = string_at(oauth, "refreshToken")

    if not oauth or not refresh_token:
        raise RuntimeError(f"Claude login expired; {profile.login_hint}")

    scopes = oauth.get("scopes")
    scope = (
        " ".join(value for value in scopes if isinstance(value, str))
        if isinstance(scopes, list)
        else DEFAULT_SCOPES
    )

    try:
        response = post_json(
            TOKEN_URL,
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": CLAUDE_CLIENT_ID,
                "scope": scope,
            },
        )
    except Exception as error:  # noqa: BLE001 - mapped to an actionable message
        detail = clean_error(error)

        if any(code in detail for code in ("HTTP 400", "HTTP 401", "HTTP 403")):
            raise RuntimeError(f"Claude login expired; {profile.login_hint}") from None

        raise RuntimeError(f"Claude token refresh failed: {detail}") from None

    access_token = apply_claude_token_response(oauth, response)
    _persist_credentials(credentials, profile)

    return access_token


def _request_usage(access_token: str) -> dict:
    body, _headers = fetch_json(
        USAGE_URL,
        {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "agent-usage-swiftbar",
        },
    )

    return body


def parse_claude_usage(body: dict) -> list[Meter]:
    meters = [
        meter
        for meter in (
            usage_meter("Weekly", body.get("seven_day")),
            usage_meter("5-hour", body.get("five_hour")),
            usage_meter("Sonnet weekly", body.get("seven_day_sonnet")),
            usage_meter("Opus weekly", body.get("seven_day_opus")),
        )
        if meter is not None
    ]
    limits = body.get("limits")

    for value in limits if isinstance(limits, list) else []:
        if not isinstance(value, dict) or string_at(value, "kind") != "weekly_scoped":
            continue

        display = (
            string_at(value, "display_name")
            or string_at(value, "scope")
            or "Model weekly"
        )
        meter = usage_meter(display, value)

        if meter and not any(
            display.lower() in existing.label.lower() for existing in meters
        ):
            meters.append(meter)

    return meters


def fetch_claude(profile: ClaudeProfile) -> ProviderResult:
    credentials = _credentials(profile)
    oauth = object_at(credentials, "claudeAiOauth")
    access_token = string_at(oauth, "accessToken")

    if not access_token:
        return ProviderResult(
            name=profile.name,
            error=f"Not logged in; {profile.login_hint}",
        )

    try:
        expires_at = number_at(oauth, "expiresAt")

        if (
            credentials
            and expires_at is not None
            and should_refresh_claude_token(expires_at)
        ):
            access_token = _refresh_token(credentials, profile)

        try:
            body = _request_usage(access_token)
        except Exception as error:  # noqa: BLE001 - one retry after a refresh
            if not credentials or clean_error(error) != "HTTP 401":
                raise

            access_token = _refresh_token(credentials, profile)
            body = _request_usage(access_token)

        meters = parse_claude_usage(body)

        if not meters:
            return ProviderResult(name=profile.name, error="No quota windows returned")

        subscription = string_at(oauth, "subscriptionType")

        return ProviderResult(
            name=profile.name,
            subtitle=subscription.upper() if subscription else None,
            meters=meters,
            activity=local_activity_windows(_collect_local_usage(profile)),
            dashboard=DASHBOARD,
        )
    except Exception as error:  # noqa: BLE001 - surfaced as a menu row
        return ProviderResult(name=profile.name, error=clean_error(error))


def _collect_local_usage(profile: ClaudeProfile) -> RollingLocalUsage:
    usage = empty_rolling_local_usage()
    now = now_ms()
    ownership = _desktop_session_ownership()
    additional = {s for s, owner in ownership.items() if owner == profile.config_dir}
    excluded = {s for s, owner in ownership.items() if owner != profile.config_dir}

    for event in collect_claude_usage_events(
        profile.config_dir,
        profile_suffix(profile),
        now,
        additional_session_ids=additional,
        excluded_session_ids=excluded,
    ):
        accumulate_rolling_usage(
            usage,
            LocalUsageEvent(
                timestamp=event.timestamp,
                total_tokens=event.total_tokens,
                uncached_tokens=event.uncached_tokens,
            ),
            now,
        )

    return usage


def _desktop_session_ownership() -> dict[str, str]:
    ownership = {}

    for profile in _registered_profiles:
        if not profile.desktop_data_dir:
            continue

        for session_id in claude_desktop_session_ids(profile.desktop_data_dir):
            ownership[session_id] = profile.config_dir

    return ownership
