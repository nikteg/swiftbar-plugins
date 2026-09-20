"""Collects provider extensions concurrently without knowing what they are."""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from .types import ProviderExtension, ProviderResult
from .utils import clean_error


def collect_provider_results(
    extensions: Sequence[ProviderExtension],
) -> list[ProviderResult]:
    if not extensions:
        return []

    with ThreadPoolExecutor(max_workers=len(extensions)) as pool:
        futures = [pool.submit(extension.collect) for extension in extensions]
        results = []

        for extension, future in zip(extensions, futures, strict=True):
            try:
                result = future.result()
                result.extension_id = result.extension_id or extension.id
            except Exception as error:  # noqa: BLE001 - one provider must not break the menu
                result = ProviderResult(
                    name=extension.name,
                    extension_id=extension.id,
                    error=clean_error(error),
                )

            results.append(result)

    return results
