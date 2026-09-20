"""What a plugin file needs from this package: collection and cache actions.

No menu code lives in this package. The plugin file owns every component and
assembles the tree itself, so the shape of the dropdown is visible where it is
configured.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence

from .cache import clear_session_caches
from .config import CACHE_DIR
from .registry import collect_provider_results
from .types import ProviderExtension, ProviderResult


def collect(extensions: Sequence[ProviderExtension]) -> list[ProviderResult]:
    """Queries every provider in parallel, isolating one provider's failure."""
    return collect_provider_results(list(extensions))


def plugin_path() -> str:
    """This plugin's own path, for menu actions that re-invoke it."""
    return os.path.realpath(sys.argv[0])


def clear_cache_requested(argv: Sequence[str] | None = None) -> bool:
    """True when SwiftBar re-invoked the plugin for the cache-clearing action."""
    argv = list(sys.argv[1:] if argv is None else argv)

    return bool(argv) and argv[0] == "--clear-cache"


def clear_cache() -> str:
    removed = clear_session_caches(CACHE_DIR)

    return f"Cleared {removed} local usage cache file(s)."
