# SwiftBar plugins

My [SwiftBar](https://github.com/swiftbar/SwiftBar) plugins, in Python, sharing
one small toolkit.

```
plugins/              one self-contained file per plugin
plugins/swiftbar_lib/ the toolkit every plugin shares
plugins/agent_usage/  agent-usage's data collection; no menu code
tests/                offline test suite
```

A plugin is one file: how it gets its data, the components it needs, and the
menu itself at the bottom. Every plugin documents itself, so open the file to
see what it shows, what you can configure and where its data comes from. The examples below are the actual
output each one prints — SwiftBar reads a line of text, then `---`, then the
dropdown, with `key=value` attributes after a `|`.

## Install

```bash
make install
```

Symlinks every plugin into `~/swiftbar`, so an edit here takes effect on the
next refresh with nothing to rebuild. `make uninstall` removes them, `make
list` prints what would be installed. Override the destination with
`make install PLUGIN_DIR="$HOME/Library/Application Support/SwiftBar/Plugins"`.

A plugin's refresh interval is the `15m` / `1h` part of its filename, so
renaming the file changes it.

---

## [agent-usage.15m.py](plugins/agent-usage.15m.py)

Coding agent subscription quotas and local spend. One circle per provider in
the menu bar, coloured by its worst quota. Implementation lives in
[plugins/agent_usage/](plugins/agent_usage/), a package because a provider
registry, a pricing catalogue and a transcript cache do not fit one file.

```
● ● ● ●
---
● Claude Default · TEAM
Weekly: ●○○○○○○○○○○○ 5% used · resets Thu Sep 24 19:00 (in 4d 3h)
  └ 1B processed tokens · 11.3M uncached tokens · 3317 calls · local activity
5-hour: ●○○○○○○○○○○○ 5% used · resets 20:10 (in 4h 32m)
Model weekly: ○○○○○○○○○○○○ 0% used · resets Thu Sep 24 19:00 (in 4d 3h)
---
● Claude Personal · PRO
Weekly: ●●○○○○○○○○○○ 13% used · resets Mon Sep 21 04:00 (in 12h 37m)
---
● Codex
⚠ Not logged in; run codex login
---
● DeepSeek
⚠ No API key in Pi auth
```

Providers are composed in the `run()` call at the bottom of the plugin file, in
display order:

```python
run(
    claude(),  # ~/.claude
    claude(ClaudeProfile(name="Claude Personal", config_dir=f"{HOME}/.pclaude")),
    codex(),
    deepseek(),
    show_clear_cache=True,
)
```

Credentials are read where each agent already stores them — the Claude Code
Keychain entry, the Codex and Kimi auth files, the Pi auth file for DeepSeek —
and nothing is written back except a refreshed OAuth token. OpenAI prices are
fetched on demand and cached for a month, falling back to a stale cache and
then to no cost estimates.

---

## [hn.1h.py](plugins/hn.1h.py)

Hacker News posts over a score threshold, with a macOS notification the first
time each one crosses it.

```
HN (3)
---
🔥 1662 - AI-generated posters don't have to be horrible | href=https://john.hartnup.uk/... length=60
--💬 View HN comments | href=https://news.ycombinator.com/item?id=49764791
--⏱️ 12h left
🔥 1245 - I built non-autoregressive decision models with RL a year ago | href=https://laya.convaiinnovations.com/ length=60
--💬 View HN comments | href=https://news.ycombinator.com/item?id=49765348
--⏱️ 12h left
---
Refresh | refresh=true
```

`run(min_score=700, display_hours=12)`. Seen posts are remembered in
`~/Library/Caches/swiftbar-plugins/hn/posts.json` so they are not re-notified;
a cold start that matches dozens summarises them into one banner instead of a
burst.

---

## [kubecontext.1m.py](plugins/kubecontext.1m.py)

The active kubeconfig context, and a menu to switch. Clicking a row runs
`kubectl config use-context` and refreshes.

```
prod-cluster
---
○ colima | refresh=true bash=/opt/homebrew/bin/kubectl param1=config param2=use-context param3=colima
● prod-cluster/api.example.com:6443/me@example.com | refresh=true bash=/opt/homebrew/bin/kubectl param1=config ...
○ staging-cluster/api.example.com:6443/me@example.com | refresh=true bash=/opt/homebrew/bin/kubectl param1=config ...
```

`run(short_names=True)` trims the menu bar label at the first `/`, which is
what keeps an ARN-style context readable. Needs `kubectl`; a missing one is
reported in the dropdown rather than failing silently.

---

## [pollen.1h.py](plugins/pollen.1h.py)

Pollen levels for a Swedish city, as a percentage of the 7-point scale.

```
🌿 Björk 0%
---
Al 0%
Alm 0%
Ambrosia 0%
Björk 0%
Bok 0%
Ek 0%
Gråbo 0%
Gräs 0%
Hassel 0%
Sälg/Vide 0%
```

`run(city="Göteborg", highlight=("bjork",))` — `highlight` picks what reaches
the menu bar; it falls back to the worst pollen of the day. Data from
pollenkoll.se.

---

## [soltid.1h.py](plugins/soltid.1h.py)

How long you can stay in the sun before burning, from
Strålsäkerhetsmyndigheten.

```
☀️ 1h 45m
---
Så många timmar och minuter kan du vistas ute i/på Sverige (Göteborg)
1h 45m i direkt solljus
Resten av dagen i lite skugga
Resten av dagen i mycket skugga
```

`run(latitude=57.71, longitude=11.0, skin_type=2)` — `skin_type` is the
Fitzpatrick scale 1-6, as on the agency's own form. Shows ✅ when the UV index
is low enough that the rest of the day is safe.

---

## [goldenhour.1h.py](plugins/goldenhour.1h.py)

This evening's golden hour.

```
🌇 18:28 - 19:18 🌇
---
Göteborg, Sweden | href=https://meteogram.org/sun/sweden/goteborg/
```

`run(country="sweden", city="goteborg")` — the path segments of a
meteogram.org sun page. Scraped with stdlib `html.parser`, since the site has
no API; a redesign of that page is what will break this one.

---

## [spotifyvolume.5m.py](plugins/spotifyvolume.5m.py)

Read and set Spotify's volume, rounded to the nearest ten so the label does not
jitter.

```
🔉 30%
---
20% | bash=spotify_volume param1=set param2=20 terminal=false refresh=true
30% | bash=spotify_volume param1=set param2=30 terminal=false refresh=true checked=true
50% | bash=spotify_volume param1=set param2=50 terminal=false refresh=true
70% | bash=spotify_volume param1=set param2=70 terminal=false refresh=true
```

When Spotify is closed, or the `spotify_volume` helper is not on `PATH`:

```
Spotify
---
spotify_volume not found on PATH
```

---

## How plugins run

Plugins are stdlib-only and carry [PEP 723](https://peps.python.org/pep-0723/)
metadata in the shebang:

```python
#!/usr/bin/env -S /opt/homebrew/bin/uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
```

uv provisions and caches its own interpreter, which matters because SwiftBar
launches plugins from a GUI context: `PATH` is the launchd minimum, so a
version manager's shim is invisible and `/usr/bin/python3` is whatever macOS
shipped — 3.9 on current systems. Pinning here means the Python that runs a
plugin is the one it was written against. uv is referenced by absolute path for
the same reason.

There is no virtualenv and nothing to install. The toolkit lives in the same
directory as the plugin files, which is the one directory Python puts on
`sys.path` by itself, so a plugin just writes `import swiftbar_lib` with no
bootstrap at all. Putting it in a sibling `lib/` would need either a
`sys.path.insert` in every plugin or a symlink back into `plugins/`; keeping
the package next to its callers avoids both.

## The toolkit

```python
from sources import hackernews
from swiftbar_lib.output import render
from swiftbar_lib.plugin import guard
from swiftbar_lib.ui import Item, Node, Refresh, Separator, Title


def Post(post) -> Node:
    return Item(
        f"🔥 {post.score} - {post.title}",
        Item("💬 View HN comments", href=post.comments_url),  # children positional
        href=post.url,  # attributes keyword
    )


if __name__ == "__main__":
    guard(name="HN", icon="⚠️")

    min_score = 700
    posts = hackernews.popular(min_score=min_score, display_hours=12)

    print(
        render(
            [
                Title(f"HN ({len(posts)})" if posts else "HN"),
                [Post(post) for post in posts]  # a list is a fragment
                or Item("No popular posts yet"),  # `or` gives the empty case
                Separator() if posts else None,  # None renders nothing
                Refresh(),
            ]
        )
    )
```

The bottom of every plugin is its menu, readable top to bottom: one line per
row, conditionals inline the way JSX uses them, and the configuration sitting
right beside the tree it configures. A named component exists only where a row
repeats — `Post` above, `Preset` in spotifyvolume, `Context` in kubecontext.
Everything else is spelled out.

`guard` installs an excepthook, so a crash prints a readable error menu rather
than a stack trace rendered one row per traceback line. It is a separate call
rather than a wrapper taking a build callback, because the only reason such a
wrapper needs a callback is to get the failure inside its own `try`.

| Module | For |
| --- | --- |
| `ui` | The node types: `Title`, `Item`, `Separator`, `Refresh` |
| `components` | Rows that recur: `Meter`, `Action`, `Link` |
| `output` | Rendering a node tree to SwiftBar's line format, and the escaping |
| `plugin` | `guard`, the error boundary: a crash becomes an error row, not a stack trace |
| `http` | JSON/text with timeouts, parallel fetches, graceful failures |
| `data` | Reading untyped JSON without trusting its shape |
| `state` | Small JSON state files, written atomically, optionally owner-only |
| `jsonl_cache` | Reading append-only logs incrementally across runs |
| `shell` | Finding and running binaries despite SwiftBar's minimal `PATH` |
| `notify` | macOS notifications, with AppleScript quoting handled |
| `ansi` | Semantic colours for menu rows |
| `meters` | Progress bars and compact number formatting |
| `dates` | Parsing the timestamp shapes APIs return |

Escaping is the reason the toolkit exists: SwiftBar splits a row on its first
`|`, so any title containing one silently truncates. `Menu` handles that
everywhere, which none of these plugins did before.

## Adding a plugin

Copy the shebang block from an existing plugin, write a module docstring that
documents it, write a component that returns a node tree, and call it under
`if __name__ == "__main__":` so the configuration is visible in one place. Name it `<name>.<interval>.py`
under `plugins/` and run `make install`.

## Development

```bash
make test     # offline suite
make check    # lint, then run every plugin as SwiftBar would
make fmt      # format and autofix
make test-live  # hits real APIs; needs you logged in
```
