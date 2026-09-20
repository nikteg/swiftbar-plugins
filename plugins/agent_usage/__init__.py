"""Agent quota collection for the agent-usage plugin.

Local to that plugin: the toolkit in ``lib/swiftbar`` is what every plugin
shares, while this package is a package only because one file could not hold a
provider registry, a pricing catalogue and a transcript cache.

Composition
    ``agent-usage.15m.py`` imports the factories re-exported here and passes
    them to ``run()``. Argument order is display order.

        print(render(Providers(claude(), codex(), kimi(), deepseek())))

Adding a provider
    A provider is a ``ProviderExtension``: an id, a display name, the auth and
    account kinds used for labelling, and a ``collect`` callable returning a
    ``ProviderResult``. ``provider.py`` builds the common shapes so a new
    service is usually declarative:

        define_provider(
            id="example",
            name="Example",
            account_type="api",
            auth=api_key_auth(source=EnvSecret("EXAMPLE_API_KEY")),
            quota=custom_quota(fetch_example_balance),
        )

    Secrets come from ``EnvSecret``, ``JsonFileSecret``, ``ValueSecret`` or
    ``CustomSecret``; none of them write anything back except the Claude OAuth
    refresh, which updates the Keychain entry in place.

Layout
    providers/  one module per service, each owning its auth and quota calls
    sources/    session-transcript readers, provider-neutral
    pricing/    model price catalogue and cost maths
    registry.py collects every extension in parallel, isolating failures
    render.py   turns results into menu rows
"""

from .cli import clear_cache, clear_cache_requested, collect, plugin_path
from .providers.claude import ClaudeProfile
from .providers.claude import create_claude_extension as claude
from .providers.codex import CodexOptions
from .providers.codex import create_codex_extension as codex
from .providers.deepseek import create_deepseek_extension as deepseek
from .providers.kimi import create_kimi_extension as kimi
from .render import ClearCache, Icon, Provider

__all__ = [
    "ClaudeProfile",
    "CodexOptions",
    "claude",
    "codex",
    "deepseek",
    "kimi",
    "ClearCache",
    "Icon",
    "Provider",
    "clear_cache",
    "collect",
    "plugin_path",
    "clear_cache_requested",
]
