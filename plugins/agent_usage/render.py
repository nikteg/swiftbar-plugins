"""Turns collected provider results into SwiftBar menu output."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from .config import BAR_WIDTH, MENU_COLORS
from .types import ActivityWindow, ProviderExtension, ProviderResult
from .utils import (
    MS_PER_MINUTE,
    clamp_percent,
    compact_number,
    round_half_up,
    swiftbar_escape,
)

ANSI_RESET = "\x1b[0m"
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


@dataclass
class RenderOptions:
    #: Absolute plugin path invoked by the optional cache-clearing menu action.
    clear_cache_command: str | None = None


def usage_level(used_percent: float) -> str:
    if used_percent >= 90:
        return "critical"

    if used_percent >= 75:
        return "warning"

    return "normal"


def _bar(used_percent: float) -> str:
    filled = int(round_half_up(clamp_percent(used_percent) / 100 * BAR_WIDTH))

    return "●" * filled + "○" * (BAR_WIDTH - filled)


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


def _ansi(text: str, color: int | str, prefix: str = "") -> str:
    return f"\x1b[{color}m{prefix}{swiftbar_escape(text)}{ANSI_RESET}"


def _usage_bar_line(label: str, used_percent: float, detail: str = "") -> str:
    used = int(round_half_up(used_percent))
    title = swiftbar_escape(f"{label}: {_bar(used)} {used}% used{detail}")
    color = MENU_COLORS[usage_level(used)]

    return f"{_ansi(title, color)} | ansi=true font=Menlo"


def _extension_for(
    result: ProviderResult, extensions: Sequence[ProviderExtension]
) -> ProviderExtension | None:
    by_id = next((e for e in extensions if e.id == result.extension_id), None)

    return by_id or next((e for e in extensions if e.name == result.name), None)


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


def _result_usage_color(
    result: ProviderResult, extensions: Sequence[ProviderExtension]
) -> int:
    if result.meters:
        return MENU_COLORS[usage_level(max(m.used_percent for m in result.meters))]

    extension = _extension_for(result, extensions)
    local = [
        percent
        for percent in (_budget_percent(extension, a) for a in result.activity)
        if percent is not None
    ]

    if local:
        return MENU_COLORS[usage_level(max(local))]

    if any(a.total_tokens > 0 or a.calls > 0 for a in result.activity):
        return MENU_COLORS["activity"]

    if result.error:
        return MENU_COLORS["critical"]

    return MENU_COLORS["unknown"]


def _result_icon(
    result: ProviderResult, extensions: Sequence[ProviderExtension]
) -> str:
    return f"\x1b[{_result_usage_color(result, extensions)}m●{ANSI_RESET}"


def _activity_lines(
    activity: ActivityWindow,
    extension: ProviderExtension | None,
    has_matching_meter: bool = False,
) -> list[str]:
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
    local_activity = "{} | ansi=true font=Menlo".format(
        _ansi(details + " · local activity", MENU_COLORS["unknown"], "  └ ")
    )
    budget = None

    if extension is not None and extension.activity is not None:
        if extension.activity.budget_info is not None:
            budget = extension.activity.budget_info(activity)

    if budget is None or has_matching_meter:
        return [local_activity]

    reset = (
        f" · resets on {activity.resets_on}"
        if activity.resets_on
        else _format_reset(activity.resets_at)
    )

    return [
        _usage_bar_line(
            activity.label,
            budget.used_percent,
            f" · {budget.detail}{reset}",
        ),
        local_activity,
    ]


def render_results(
    results: Sequence[ProviderResult],
    extensions: Sequence[ProviderExtension],
    options: RenderOptions | None = None,
) -> str:
    options = options or RenderOptions()
    icons = " ".join(_result_icon(result, extensions) for result in results)
    output = [
        f"{icons} | ansi=true symbolize=false font=Menlo size=13 dropdown=false",
        "---",
    ]

    for index, result in enumerate(results):
        output.extend(_result_lines(result, extensions))

        if index < len(results) - 1:
            output.append("---")

    if options.clear_cache_command:
        if results:
            output.append("---")

        output.append(
            "Clear local usage caches"
            f" | bash={_attribute(options.clear_cache_command)} param1=--clear-cache "
            "terminal=false refresh=true"
        )

    return "\n".join(output)


def _result_lines(
    result: ProviderResult, extensions: Sequence[ProviderExtension]
) -> list[str]:
    heading = f"{result.name} · {result.subtitle}" if result.subtitle else result.name
    action = f" href={result.dashboard}" if result.dashboard else ""
    output = [
        f"{_result_icon(result, extensions)} {swiftbar_escape(heading)}"
        f" | ansi=true symbolize=false size=13 font=Menlo{action}"
    ]

    if result.error:
        output.append(
            "{} | ansi=true".format(_ansi("⚠ " + result.error, MENU_COLORS["critical"]))
        )

    extension = _extension_for(result, extensions)
    pending = list(result.activity)

    for meter in result.meters:
        detail = f" · {meter.detail}" if meter.detail else ""
        output.append(
            _usage_bar_line(
                meter.label,
                meter.used_percent,
                detail + _format_reset(meter.resets_at),
            )
        )
        matching = [a for a in pending if a.label == meter.label]

        for activity in matching:
            output.extend(_activity_lines(activity, extension, True))
            pending.remove(activity)

    for activity in pending:
        output.extend(_activity_lines(activity, extension))

    for detail_line in result.details:
        if detail_line.ansi_color is None:
            title, ansi = swiftbar_escape(detail_line.text), ""
        else:
            title, ansi = _ansi(detail_line.text, detail_line.ansi_color), " ansi=true"

        font = f" font={detail_line.font}" if detail_line.font else ""
        output.append(f"{title} |{ansi}{font}")

    output.extend(swiftbar_escape(line) for line in result.lines)

    return output


def _attribute(value: str) -> str:
    return '"{}"'.format(value.replace("\\", "\\\\").replace('"', '\\"'))
