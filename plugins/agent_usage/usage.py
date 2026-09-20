"""Rolling windows over locally measured usage events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .types import ActivityWindow, LocalUsage, LocalUsageEvent, RollingLocalUsage
from .utils import MS_PER_DAY, MS_PER_HOUR

DEFAULT_PERIOD_MS = 30 * MS_PER_DAY


@dataclass
class MonthlyCycle:
    """The billing period a monthly activity estimate is measured against."""

    started_at: float
    resets_at: datetime


def empty_local_usage(credits: bool = False, cost: bool = False) -> LocalUsage:
    return LocalUsage(credits=0.0 if credits else None, cost=0.0 if cost else None)


def empty_rolling_local_usage(
    credits: bool = False, cost: bool = False
) -> RollingLocalUsage:
    return RollingLocalUsage(
        five_hour=empty_local_usage(credits, cost),
        seven_day=empty_local_usage(credits, cost),
        period=empty_local_usage(credits, cost),
    )


def add_local_usage(target: LocalUsage, event: LocalUsageEvent) -> None:
    target.total_tokens += event.total_tokens
    target.uncached_tokens += event.uncached_tokens
    target.calls += 1

    if target.credits is not None or event.credits is not None:
        target.credits = (target.credits or 0.0) + (event.credits or 0.0)

    if target.cost is not None or event.cost is not None:
        target.cost = (target.cost or 0.0) + (event.cost or 0.0)


def accumulate_rolling_usage(
    target: RollingLocalUsage,
    event: LocalUsageEvent,
    now: float,
    period_start: float | None = None,
) -> None:
    if period_start is None:
        period_start = now - DEFAULT_PERIOD_MS

    age = now - event.timestamp

    if age < 0:
        return

    if event.timestamp >= period_start:
        add_local_usage(target.period, event)

    if age <= 7 * MS_PER_DAY:
        add_local_usage(target.seven_day, event)

    if age <= 5 * MS_PER_HOUR:
        add_local_usage(target.five_hour, event)


def merge_rolling_usage(
    left: RollingLocalUsage, right: RollingLocalUsage
) -> RollingLocalUsage:
    return RollingLocalUsage(
        five_hour=_merge(left.five_hour, right.five_hour),
        seven_day=_merge(left.seven_day, right.seven_day),
        period=_merge(left.period, right.period),
    )


def _merge(left: LocalUsage, right: LocalUsage) -> LocalUsage:
    return LocalUsage(
        total_tokens=left.total_tokens + right.total_tokens,
        uncached_tokens=left.uncached_tokens + right.uncached_tokens,
        calls=left.calls + right.calls,
        credits=_add_optional(left.credits, right.credits),
        cost=_add_optional(left.cost, right.cost),
    )


def _add_optional(left: float | None, right: float | None) -> float | None:
    if left is None and right is None:
        return None

    return (left or 0.0) + (right or 0.0)


def _window(label: str, usage: LocalUsage, **extra) -> ActivityWindow:
    return ActivityWindow(
        label=label,
        total_tokens=usage.total_tokens,
        uncached_tokens=usage.uncached_tokens,
        calls=usage.calls,
        credits=usage.credits,
        cost=usage.cost,
        **extra,
    )


def local_activity_windows(usage: RollingLocalUsage) -> list[ActivityWindow]:
    return [_window("Weekly", usage.seven_day), _window("5-hour", usage.five_hour)]


def monthly_activity_windows(
    usage: RollingLocalUsage, cycle: MonthlyCycle | None = None
) -> list[ActivityWindow]:
    return [
        _window(
            "Monthly" if cycle else "Rolling 30-day",
            usage.period,
            resets_at=cycle.resets_at if cycle else None,
        ),
        _window("Weekly", usage.seven_day),
        _window("5-hour", usage.five_hour),
    ]
