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
menu itself at the bottom. Each one documents itself, so open the file to see
what it shows, what you can configure and where its data comes from.

SwiftBar reads stdout: the menu bar line, then `---`, then the dropdown, with
`key=value` attributes after a `|` and `--` per submenu level. The samples
below are real output.

## Install

```bash
make install
```

Symlinks every plugin into `~/swiftbar`, so an edit here takes effect on the
next refresh with nothing to rebuild. Override the destination with
`make install PLUGIN_DIR="$HOME/Library/Application Support/SwiftBar/Plugins"`.

A plugin's refresh interval is the `15m` / `1h` part of its filename, so
renaming the file changes it.

### Which plugins are on

Deliberately **not** in this repo. SwiftBar disables a plugin by prefixing its
filename with a period, so the answer already lives in the plugin directory as
either `name` or `.name` — the same thing SwiftBar's own Disable menu item
writes, and nothing git ever sees.

```bash
make list                          # on / off / absent, read from ~/swiftbar
make disable PLUGIN=pollen.1h.py
make enable PLUGIN=pollen.1h.py
```

`make install` never overrules that: it links only plugins it finds under
neither spelling, so running it after a `git pull` picks up anything new
without switching your disabled ones back on. `make uninstall` removes both.

---

## [agent-usage.15m.py](plugins/agent-usage.15m.py)

Coding agent subscription quotas and local spend: one circle per provider,
coloured by its worst quota — green under 75%, amber under 90%, red above, and
red for a provider that failed.

```
● ● ● ●
---
● Claude Default · TEAM
Weekly: ●○○○○○○○○○○○ 6% used · resets Thu Sep 24 19:00 (in 4d 2h)
  └ 1.1B processed tokens · 11.7M uncached tokens · 3459 calls · local activity
5-hour: ●○○○○○○○○○○○ 12% used · resets 20:10 (in 3h 22m)
---
● Codex
⚠ Not logged in; run codex login
---
● DeepSeek
Weekly: ○○○○○○○○○○○○ 0% used · budget $5
3.62 USD available
---
Clear local usage caches
```

Providers are listed and rendered in the plugin file; the package behind it
collects and never draws:

```python
claude_default, claude_personal, codex, deepseek = collect(
    providers.claude(ClaudeProfile(name="Claude Default", config_dir=f"{HOME}/.claude", ...)),
    providers.claude(ClaudeProfile(name="Claude Personal", config_dir=f"{HOME}/.pclaude", ...)),
    providers.codex(),
    providers.deepseek(),
)

show(
    Circles(Icon(claude_default), Icon(claude_personal), Icon(codex), Icon(deepseek)),
    ProviderUsage(claude_default),
    Separator(),
    ProviderUsage(claude_personal),
    ...
    Action("Clear local usage caches", plugin_path(), "--clear-cache"),
)
```

`collect` returns each provider paired with what it reported, so a component
takes one value. Argument order is the order of the circles and of the
dropdown sections.

Credentials are read where each agent already stores them — the Claude Code
Keychain entry, the Codex and Kimi auth files, the Pi auth file for DeepSeek —
and nothing is written back except a refreshed OAuth token. OpenAI prices are
fetched on demand and cached for a month, falling back to a stale cache and
then to no cost estimates. `agent_usage/` is a package because a provider
registry, a pricing catalogue and a transcript cache do not fit in one file.

---

## [hn.1h.py](plugins/hn.1h.py)

Hacker News posts over a score threshold, with a macOS notification the first
time each one crosses it.

```
HN (3)
---
🔥 1662 - AI-generated posters don't have to be horrible | href=https://john.hartnup.uk/... length=60
--💬 View HN comments | href=https://news.ycombinator.com/item?id=49764791
--⏱️ 11h left
---
Refresh | refresh=true
```

```python
posts = popular(min_score=700, display_hours=12, cleanup_days=7, check_limit=50)

show(
    Title(f"HN ({len(posts)})" if posts else "HN"),
    [Story(post, display_hours, now) for post in posts]
    or [Item("No popular posts yet"), Item(f"(waiting for posts with {min_score}+ points)")],
    Separator(),
    Refresh(),
)
```

Seen posts are remembered in `~/Library/Caches/swiftbar-plugins/hn/posts.json`
so they are not re-notified. They leave the menu after `display_hours` but stay
in that file for `cleanup_days`; the gap is what stops an old post being
announced again if it resurfaces. A cold start matching dozens summarises them
into one banner instead of a burst.

---

## [kubecontext.1m.py](plugins/kubecontext.1m.py)

The active kubeconfig context, and a menu to switch. Clicking a row runs
`kubectl config use-context` and refreshes.

```
prod-cluster
---
○ colima | bash=/opt/homebrew/bin/kubectl param1=config param2=use-context param3=colima terminal=false refresh=true
● prod-cluster/api.example.com:6443/me@example.com | bash=/opt/homebrew/bin/kubectl ... terminal=false refresh=true
```

`short_names = True` trims the menu bar label at the first `/`, which keeps an
ARN-style context readable. Needs `kubectl`; a missing one is reported in the
dropdown rather than failing silently.

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
...
```

Every pollen is one line, so reordering, renaming or dropping one is a line:

```python
today = levels("Göteborg")

show(
    Title(f"🌿 Björk {today['bjork']}"),
    Item(f"Al {today['al']}"),
    Item(f"Alm {today['alm']}"),
    ...
)
```

`today` defaults to `—` for anything unreported, so the rows render even when
the city has no data. Source: pollenkoll.se.

---

## [soltid.1h.py](plugins/soltid.1h.py)

How long you can stay in the sun before burning, from
Strålsäkerhetsmyndigheten. ✅ when the UV index is low enough that the rest of
the day is safe.

```
☀️ ✅
---
Så många timmar och minuter kan du vistas ute i/på Sverige (Göteborg)
Resten av dagen i direkt solljus
Resten av dagen i lite skugga
Resten av dagen i mycket skugga
```

`forecast(latitude=57.71, longitude=11.0, skin_type=2)` — `skin_type` is the
Fitzpatrick scale 1-6, as on the agency's own form.

---

## [goldenhour.1h.py](plugins/goldenhour.1h.py)

This evening's golden hour.

```
🌇 18:28 - 19:18 🌇
---
Göteborg, Sweden | href=https://meteogram.org/sun/sweden/goteborg/
```

`evening(country="sweden", city="goteborg")` — the path segments of a
meteogram.org sun page. Scraped with stdlib `html.parser`, since the site has
no API; a redesign of that page is what will break this one.

---

## [spotifyvolume.5m.py](plugins/spotifyvolume.5m.py)

Read and set Spotify's volume, rounded to the nearest ten so the label does not
jitter. Each preset is one line.

```
🔉 30%
---
20% | bash=/Users/you/.bin/spotify_volume param1=set param2=20 terminal=false refresh=true checked=false
30% | bash=/Users/you/.bin/spotify_volume param1=set param2=30 terminal=false refresh=true checked=true
```

With Spotify closed, or the `spotify_volume` helper missing:

```
Spotify
---
spotify_volume not on PATH
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

There is no virtualenv and nothing to install. The toolkit sits in the same
directory as the plugin files, which is the one directory Python puts on
`sys.path` by itself, so a plugin just writes `import swiftbar_lib` with no
bootstrap at all. Putting it in a sibling `lib/` would need either a
`sys.path.insert` in every plugin or a symlink back into `plugins/`.

Nothing catches plugin-level errors: a crash exits non-zero and SwiftBar shows
the failure itself. `clean_error` is only for a failure a plugin wants to
render as a row, such as one provider of several being unreachable.

## The toolkit

Rendering is declarative. Components are plain functions returning nodes; the
menu is written out at the bottom of the plugin, readable top to bottom.

```python
def Story(post, display_hours, now) -> Node:
    return Item(
        f"🔥 {post.score} - {post.title}",
        Item("💬 View HN comments", href=post.comments_url),  # children positional
        Item(f"⏱️ {post.hours_left(display_hours, now):.0f}h left"),
        href=post.url,                                        # attributes keyword
        length=60,
    )
```

Conditionals go inline the way JSX uses them: `Title(a) if cond else Title(b)`
for a branch, `[...] or Item("nothing")` for the empty case, `None` for a row
that is not there. A list is a fragment. `show` prints; `render` returns the
string, which is what the tests use. Both are variadic.

Where the rows are a fixed set they are written out one per line. A
comprehension is only for a list whose length the data decides — the posts in
hn, the contexts in kubecontext, the hours in soltid. A named component exists
only where a row repeats: `Story` here, `Preset` in spotifyvolume, `Switch` in
kubecontext, `ProviderUsage` in agent-usage.

| Module | For |
| --- | --- |
| `ui` | The node types: `Title`, `Item`, `Separator`, `Refresh` |
| `components` | Rows that recur: `Meter`, `Action`, `Link` |
| `output` | Rendering a node tree to SwiftBar's line format, and the escaping |
| `errors` | `clean_error`, for a failure a plugin renders as a row |
| `http` | JSON/text with timeouts, parallel fetches, graceful failures |
| `data` | Reading untyped JSON without trusting its shape |
| `state` | Small JSON state files, written atomically, optionally owner-only |
| `jsonl_cache` | Reading append-only logs incrementally across runs |
| `shell` | Finding and running binaries despite SwiftBar's minimal `PATH` |
| `notify` | macOS notifications, with AppleScript quoting handled |
| `ansi` | Semantic colours for menu rows |
| `meters` | Progress bars and compact number formatting |
| `dates` | Parsing the timestamp shapes APIs return |

Escaping is a large part of why the toolkit exists. SwiftBar splits a row on
its first `|`, so any text containing one silently truncates, and it splits
into rows before it parses quotes, so a newline in an attribute value forges a
whole extra row. `render` strips both from labels and attributes, keeping ESC
in labels so a coloured row still works; `escape_strict` removes that too and
is what provider-controlled text goes through.

## Adding a plugin

Copy the shebang block from an existing plugin, write a module docstring that
documents it, and build the menu under `if __name__ == "__main__":` so the
configuration sits beside the tree it configures. Name it
`<name>.<interval>.py` under `plugins/` and run `make install`.

## Development

```bash
make test       # offline suite, no network
make check      # lint, then run every plugin as SwiftBar would
make fmt        # format and autofix
make test-live  # hits real APIs; needs you logged in
```

`make test` is hermetic: a fixture freezes OpenAI's price list, so the suite
passes with the network down and does not assert on what pricing says today.
