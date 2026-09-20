"""Declarative building blocks for providers with ordinary auth and quotas."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .types import ActivityExtension, ProviderExtension, ProviderResult
from .utils import clean_error, fetch_json, object_at, read_json, string_at


@dataclass
class AuthAdapter:
    type: str
    authorize: Callable[[], dict[str, str]]


@dataclass
class QuotaAdapter:
    type: str
    #: ``(auth_headers) -> ProviderResult``
    collect: Callable[[dict[str, str]], ProviderResult]


def define_provider(
    id: str,
    name: str,
    account_type: str,
    auth: AuthAdapter,
    quota: QuotaAdapter,
    activity: ActivityExtension | None = None,
) -> ProviderExtension:
    """Builds a provider whose declarations drive collection."""

    def collect() -> ProviderResult:
        try:
            result = quota.collect(auth.authorize())
        except Exception as error:  # noqa: BLE001 - surfaced as a menu row
            return ProviderResult(name=name, error=clean_error(error))

        result.name = result.name or name

        return result

    return ProviderExtension(
        id=id,
        name=name,
        auth_type=auth.type,
        account_type=account_type,
        quota_type=quota.type,
        collect=collect,
        activity=activity,
    )


def no_auth(headers: Mapping[str, str] | None = None) -> AuthAdapter:
    return AuthAdapter(type="none", authorize=lambda: dict(headers or {}))


def custom_auth(type: str, authorize: Callable[[], dict[str, str]]) -> AuthAdapter:
    return AuthAdapter(type=type, authorize=authorize)


def custom_quota(type: str, collect: Callable[..., ProviderResult]) -> QuotaAdapter:
    return QuotaAdapter(type=type, collect=collect)


@dataclass
class EnvSecret:
    variable: str

    def resolve(self) -> str | None:
        return os.environ.get(self.variable) or None


@dataclass
class ValueSecret:
    value: str

    def resolve(self) -> str | None:
        return self.value or None


@dataclass
class JsonFileSecret:
    path: str
    keys: list[str]

    def resolve(self) -> str | None:
        value: Any = read_json(self.path)

        for key in self.keys[:-1]:
            value = object_at(value, key)

        return string_at(value, self.keys[-1]) if self.keys else None


@dataclass
class CustomSecret:
    resolve: Callable[[], str | None]


def api_key_auth(
    source,
    header: str = "Authorization",
    scheme: str | None = None,
    missing_message: str = "API key is not configured",
    headers: Mapping[str, str] | None = None,
) -> AuthAdapter:
    def authorize() -> dict[str, str]:
        secret = source.resolve()

        if not secret:
            raise RuntimeError(missing_message)

        value = f"{scheme} {secret}" if scheme else secret

        return {**dict(headers or {}), header: value}

    return AuthAdapter(type="api-key", authorize=authorize)


def http_json_quota(
    type: str,
    url: str,
    parse: Callable[[dict, Mapping[str, str]], ProviderResult],
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    on_error: Callable[[BaseException], ProviderResult] | None = None,
) -> QuotaAdapter:
    def collect(auth_headers: dict[str, str]) -> ProviderResult:
        try:
            body, response_headers = fetch_json(
                url, {**dict(headers or {}), **auth_headers}, method
            )

            return parse(body, response_headers)
        except Exception as error:  # noqa: BLE001 - optional degraded result
            if on_error is None:
                raise

            result = on_error(error)
            result.error = result.error or clean_error(error)

            return result

    return QuotaAdapter(type=type, collect=collect)
