"""Data carried between providers, the registry, and the plugin file."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Meter:
    """A quota window the provider itself reports."""

    label: str
    used_percent: float
    resets_at: datetime | None = None
    detail: str | None = None


@dataclass
class ActivityWindow:
    """Usage this plugin measured locally from session logs."""

    label: str
    total_tokens: float = 0.0
    uncached_tokens: float = 0.0
    calls: int = 0
    credits: float | None = None
    cost: float | None = None
    resets_at: datetime | None = None
    resets_on: str | None = None


@dataclass
class DetailLine:
    text: str
    ansi_color: int | None = None
    font: str | None = None


@dataclass
class ProviderResult:
    name: str
    extension_id: str | None = None
    dashboard: str | None = None
    subtitle: str | None = None
    meters: list[Meter] = field(default_factory=list)
    activity: list[ActivityWindow] = field(default_factory=list)
    details: list[DetailLine] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class LocalBudgetInfo:
    used_percent: float
    detail: str


@dataclass
class ActivityExtension:
    """Provider-owned interpretation of its own local activity windows."""

    budget_info: Callable[[ActivityWindow], LocalBudgetInfo | None] | None = None
    detail_lines: Callable[[ActivityWindow], list[str]] | None = None


@dataclass
class ProviderExtension:
    """A provider collector plus its auth/account/quota metadata."""

    id: str
    name: str
    auth_type: str
    account_type: str
    quota_type: str
    collect: Callable[[], ProviderResult]
    activity: ActivityExtension | None = None


@dataclass
class LocalUsage:
    total_tokens: float = 0.0
    uncached_tokens: float = 0.0
    calls: int = 0
    credits: float | None = None
    cost: float | None = None


@dataclass
class LocalUsageEvent:
    timestamp: float
    total_tokens: float
    uncached_tokens: float
    credits: float | None = None
    cost: float | None = None


@dataclass
class RollingLocalUsage:
    five_hour: LocalUsage = field(default_factory=LocalUsage)
    seven_day: LocalUsage = field(default_factory=LocalUsage)
    period: LocalUsage = field(default_factory=LocalUsage)


@dataclass(frozen=True)
class Usage:
    """A provider paired with what it just reported."""

    provider: ProviderExtension
    result: ProviderResult
