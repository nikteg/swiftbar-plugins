"""Agent quota collection for the agent-usage plugin.

Local to that plugin: the toolkit in ``lib/swiftbar`` is what every plugin
shares, while this package is a package only because one file could not hold a
provider registry, a pricing catalogue and a transcript cache.

Composition
    ``agent-usage.15m.py`` imports the factories re-exported here and passes
    them to ``run()``. Argument order is display order.

        results = collect([claude(), codex(), kimi(), deepseek()])

Rendering
    None of it lives here. The plugin file owns every component, so this
    package is collection only: providers, a registry, pricing and the
    transcript sources they read.

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
    cli.py      what a plugin file calls: collect() and the cache actions
"""

from . import providers
from .cli import clear_cache, clear_cache_requested, collect, plugin_path
from .providers.claude import ClaudeProfile
from .types import ActivityWindow, Usage

__all__ = [
    "Usage",
    "providers",
    "ActivityWindow",
    "ClaudeProfile",
    "CodexOptions",
    "clear_cache",
    "collect",
    "plugin_path",
    "clear_cache_requested",
]
