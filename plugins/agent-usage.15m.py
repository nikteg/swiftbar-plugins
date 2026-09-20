#!/usr/bin/env -S /opt/homebrew/bin/uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
# <swiftbar.title>Agent usage</swiftbar.title>
# <swiftbar.author>nikteg</swiftbar.author>
# <swiftbar.author.github>nikteg</swiftbar.author.github>
# <swiftbar.desc>Coding agent subscription quotas and local spend</swiftbar.desc>
# <swiftbar.dependencies>uv</swiftbar.dependencies>
"""Coding agent subscription quotas and local spend.

Shows
    Menu bar: one circle per provider, coloured by the worst quota it reports
    — green under 75% used, yellow under 90%, red above, grey when unknown.
    Dropdown: per provider, the plan, each quota window with a bar and its
    reset time, and local activity measured from session transcripts.

Configure
    Edit the run() call at the bottom of this file. Argument order is the
    order of the circles and of the dropdown sections, so reordering or
    dropping a provider is a one-line change.
      claude(profile)      One Claude profile. No argument uses ~/.claude.
                           Pass a ClaudeProfile for a second account; the id
                           comes from the name and only has to be unique here.
      codex(monthly_cycle_day=N)
                           N is a fallback for when the API reports no reset
                           date, without which the monthly figure is labelled
                           Rolling 30-day.
      kimi(), deepseek()   No configuration.
      show_clear_cache     Adds a dropdown action that deletes the usage
                           caches, for when a transcript scan goes wrong.

Credentials
    Read-only, from where each agent already stores them: the Claude Code
    Keychain entry, Codex and Kimi auth files, and the Pi auth file for
    DeepSeek. Nothing is written back except a refreshed OAuth token.

Implementation
    agent_usage/ collects the data and contains no menu code; every
    component below is this plugin's own.

Refresh
    Every 15 minutes, from the ``15m`` in this file's name.
"""

import os
from datetime import datetime

from agent_usage import (
    ActivityWindow,
    Usage,
    clear_cache,
    clear_cache_requested,
    collect,
    plugin_path,
    providers,
)
from agent_usage.providers import ClaudeProfile
from agent_usage.types import ProviderExtension
from swiftbar_lib.ansi import COLORS, RESET, level_for
from swiftbar_lib.components import Action, MenuBar, Meter
from swiftbar_lib.dates import MONTHS, MS_PER_MINUTE, WEEKDAYS
from swiftbar_lib.meters import compact_number
from swiftbar_lib.output import escape_strict, show
from swiftbar_lib.plugin import guard
from swiftbar_lib.ui import Item, Node, Separator

HOME = os.environ.get("HOME", "")


def _ansi(text: str, color: int | str, prefix: str = "") -> str:
    return f"\x1b[{color}m{prefix}{escape_strict(text)}{RESET}"


def _format_reset(date: datetime | None) -> str:
    if date is None:
        return ""

    milliseconds = (date - datetime.now(date.tzinfo)).total_seconds() * 1000

    if milliseconds <= 0:
        return " · reset due"

    minutes = -(-int(milliseconds) // MS_PER_MINUTE)  # ceil
    days, remainder = divmod(minutes, 1440)
    hours, mins = divmod(remainder, 60)

    if days > 0:
        relative = f"in {days}d {hours}h"
    elif hours > 0:
        relative = f"in {hours}h {mins}m"
    else:
        relative = f"in {mins}m"

    return f" · resets {_format_local_reset(date)} ({relative})"


def _format_local_reset(date: datetime) -> str:
    local = date.astimezone()
    time = f"{local.hour:02d}:{local.minute:02d}"
    now = datetime.now(local.tzinfo)

    if (local.year, local.month, local.day) == (now.year, now.month, now.day):
        return time

    return f"{WEEKDAYS[local.weekday()]} {MONTHS[local.month - 1]} {local.day} {time}"


def _budget_percent(
    extension: ProviderExtension | None, activity: ActivityWindow
) -> float | None:
    if extension is None or extension.activity is None:
        return None

    budget_info = extension.activity.budget_info

    if budget_info is None:
        return None

    info = budget_info(activity)

    return None if info is None else info.used_percent


def _usage_color(usage: Usage) -> int:
    result, extension = usage.result, usage.provider

    if result.meters:
        return COLORS[level_for(max(m.used_percent for m in result.meters))]

    local = [
        percent
        for percent in (_budget_percent(extension, a) for a in result.activity)
        if percent is not None
    ]

    if local:
        return COLORS[level_for(max(local))]

    if any(a.total_tokens > 0 or a.calls > 0 for a in result.activity):
        return COLORS["activity"]

    if result.error:
        return COLORS["critical"]

    return COLORS["unknown"]


def Icon(usage: Usage) -> str:
    """The menu bar circle, coloured by the worst quota this provider reports."""
    return f"\x1b[{_usage_color(usage)}m●{RESET}"


def Activity(
    activity: ActivityWindow,
    extension: ProviderExtension | None,
    has_matching_meter: bool = False,
) -> Node:
    extras = []

    if extension is not None and extension.activity is not None:
        if extension.activity.detail_lines is not None:
            extras = extension.activity.detail_lines(activity)

    details = " · ".join(
        [
            f"{compact_number(activity.total_tokens)} processed tokens"
            f" · {compact_number(activity.uncached_tokens)} uncached tokens"
            f" · {activity.calls} calls",
            *extras,
        ]
    )
    local = Item(
        _ansi(details + " · local activity", COLORS["unknown"], "  └ "),
        ansi=True,
        font="Menlo",
    )
    budget = None

    if extension is not None and extension.activity is not None:
        if extension.activity.budget_info is not None:
            budget = extension.activity.budget_info(activity)

    if budget is None or has_matching_meter:
        return local

    reset = (
        f" · resets on {activity.resets_on}"
        if activity.resets_on
        else _format_reset(activity.resets_at)
    )

    return [
        Meter(activity.label, budget.used_percent, f" · {budget.detail}{reset}"),
        local,
    ]


def ProviderUsage(usage: Usage) -> Node:
    result, extension = usage.result, usage.provider
    heading = f"{result.name} · {result.subtitle}" if result.subtitle else result.name
    pending = list(result.activity)
    meters: list[Node] = []

    for meter in result.meters:
        detail = f" · {meter.detail}" if meter.detail else ""
        meters.append(
            Meter(
                meter.label,
                meter.used_percent,
                detail + _format_reset(meter.resets_at),
            )
        )
        matching = [a for a in pending if a.label == meter.label]

        for activity in matching:
            meters.append(Activity(activity, extension, True))
            pending.remove(activity)

    return [
        Item(
            f"{Icon(usage)} {escape_strict(heading)}",
            ansi=True,
            symbolize=False,
            size=13,
            font="Menlo",
            href=result.dashboard or None,
        ),
        Item(_ansi("⚠ " + result.error, COLORS["critical"]), ansi=True)
        if result.error
        else None,
        meters,
        [Activity(activity, extension) for activity in pending],
        [Detail(line) for line in result.details],
        [Item(escape_strict(line)) for line in result.lines],
    ]


def Detail(line) -> Item:
    if line.ansi_color is None:
        return Item(escape_strict(line.text), font=line.font or None)

    return Item(_ansi(line.text, line.ansi_color), ansi=True, font=line.font or None)


if __name__ == "__main__":
    guard(name="Agent usage")

    if clear_cache_requested():
        print(clear_cache())
        raise SystemExit(0)

    # Order here is the order of the circles and of the dropdown sections.
    claude_default, claude_personal, codex, deepseek = collect(
        providers.claude(
            ClaudeProfile(
                name="Claude Default",
                config_dir=f"{HOME}/.claude",
                is_default=True,
                login_hint="run claude auth login",
                desktop_data_dir=f"{HOME}/Library/Application Support/Claude",
            )
        ),
        providers.claude(
            ClaudeProfile(
                name="Claude Personal",
                config_dir=f"{HOME}/.pclaude",
                is_default=False,
                login_hint="run CLAUDE_CONFIG_DIR=~/.pclaude claude auth login",
                desktop_data_dir=f"{HOME}/Library/Application Support/Claude-Personal",
            )
        ),
        providers.codex(),
        providers.deepseek(),
    )

    show(
        MenuBar(
            Icon(claude_default), Icon(claude_personal), Icon(codex), Icon(deepseek)
        ),
        ProviderUsage(claude_default),
        Separator(),
        ProviderUsage(claude_personal),
        Separator(),
        ProviderUsage(codex),
        Separator(),
        ProviderUsage(deepseek),
        Separator(),
        Action("Clear local usage caches", plugin_path(), "--clear-cache"),
    )
