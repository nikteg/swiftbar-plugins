"""JSON and text over HTTP, with timeouts and errors worth displaying."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any

DEFAULT_TIMEOUT = 12.0
USER_AGENT = "swiftbar-plugins (python urllib)"


def _open(request: urllib.request.Request, timeout: float):
    request.add_header("User-Agent", USER_AGENT)

    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"HTTP {error.code}") from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            raise TimeoutError("Request timed out") from None

        raise RuntimeError(str(error.reason)) from None


def get_text(
    url: str,
    headers: Mapping[str, str] | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    request = urllib.request.Request(url, headers=dict(headers or {}))

    with _open(request, timeout) as response:
        return response.read().decode("utf-8", "replace")


def get_json(
    url: str,
    headers: Mapping[str, str] | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    method: str = "GET",
) -> Any:
    body, _ = get_json_with_headers(url, headers, timeout=timeout, method=method)

    return body


def get_json_with_headers(
    url: str,
    headers: Mapping[str, str] | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    method: str = "GET",
) -> tuple[Any, Mapping[str, str]]:
    """Also returns response headers, for APIs that report quota in them."""
    request = urllib.request.Request(url, method=method, headers=dict(headers or {}))

    with _open(request, timeout) as response:
        return json.loads(response.read().decode("utf-8")), response.headers


def post_json(
    url: str,
    body: Any,
    headers: Mapping[str, str] | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """Posts JSON, or form-encoded pairs when ``body`` is a list of tuples."""
    is_form = isinstance(body, list)
    payload = (
        urllib.parse.urlencode(body).encode() if is_form else json.dumps(body).encode()
    )
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": (
                "application/x-www-form-urlencoded" if is_form else "application/json"
            ),
            **dict(headers or {}),
        },
    )

    with _open(request, timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def gather[T, R](
    items: Iterable[T], worker: Callable[[T], R], max_concurrency: int = 20
) -> list[R]:
    """Runs ``worker`` over ``items`` in parallel, preserving input order.

    Threads rather than asyncio: these are blocking urllib calls, and a plugin
    process is too short-lived for an event loop to earn its complexity.
    """
    materialized = list(items)

    if not materialized:
        return []

    workers = min(max_concurrency, len(materialized))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(worker, materialized))


def quiet[R](fetch: Callable[[], R], default: R) -> R:
    """Runs a fetch, substituting a default when it fails."""

    try:
        return fetch()
    except Exception:
        return default
