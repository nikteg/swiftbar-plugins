"""Plugin runtime: collect every composed provider, then render."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence

from .config import CACHE_DIR
from .registry import collect_provider_results
from .render import RenderOptions, render_results
from .session_cache import clear_session_caches
from .types import PluginOptions, ProviderExtension, ProviderResult


def fetch_provider_results(
    extensions: Sequence[ProviderExtension],
) -> list[ProviderResult]:
    return collect_provider_results(extensions)


def render(
    results: Sequence[ProviderResult],
    extensions: Sequence[ProviderExtension],
    options: PluginOptions | None = None,
    plugin_path: str | None = None,
) -> str:
    options = options or PluginOptions()

    return render_results(
        results,
        extensions,
        RenderOptions(
            clear_cache_command=(
                plugin_path or _plugin_path() if options.show_clear_cache else None
            )
        ),
    )


def _plugin_path() -> str:
    return os.path.realpath(sys.argv[0])


def run(
    *extensions: ProviderExtension,
    show_clear_cache: bool = False,
    argv: Sequence[str] | None = None,
) -> int:
    """Entrypoint for a plugin file: pass the providers to monitor, in order.

    The order of the arguments is the order of the circles in the menu bar and
    of the sections in the dropdown.
    """
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] == "--clear-cache":
        removed = clear_session_caches(CACHE_DIR)
        print(f"Cleared {removed} local usage cache file(s).")

        return 0

    composed = list(extensions)
    print(
        render(
            fetch_provider_results(composed),
            composed,
            PluginOptions(show_clear_cache=show_clear_cache),
        )
    )

    return 0
