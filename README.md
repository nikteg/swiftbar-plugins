# SwiftBar plugins

My [SwiftBar](https://github.com/swiftbar/SwiftBar) plugins, in Python, sharing
one small toolkit.

```
plugins/              one self-contained file per plugin
plugins/swiftbar_lib/ the toolkit every plugin shares
plugins/agent_usage/  agent-usage's data collection; no menu code
plugins/ci/           what github-actions and buildkite share, menu included
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

### Personal settings

Also not in this repo. What is specific to you — where you live, which repos
you watch — goes in `~/.config/swiftbar-plugins/<name>.json`, and the plugin
files keep only generic defaults. The name is the plugin's filename without its
refresh interval, so `soltid.1h.py` reads `soltid.json`, and renaming it to
change the interval keeps its settings:

```json
{ "latitude": 55.6, "longitude": 13.0, "skin_type": 3 }
```

A plugin missing a setting it has no default for says which one, and where, in
its dropdown instead of guessing.

---

## [agent-usage.15m.py](plugins/agent-usage.15m.py)

Coding agent subscription quotas and local spend: one squircle per provider,
coloured by its worst quota — green under 75%, amber under 90%, red above — and
a red warning triangle for a provider that could not be read, so a failure is
not mistaken for a full quota. The squircles are [drawn as images](#squircles).

```
| image=iVBORw0KGgo… dropdown=false
---
Claude Default · TEAM | image=iVBORw0KGgo… symbolize=false size=13 font=Menlo
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
    Bar(claude_default, claude_personal, codex, deepseek),
    ProviderUsage(claude_default),
    Separator(),
    ProviderUsage(claude_personal),
    ...
    Action("Clear local usage caches", plugin_path(), "--clear-cache"),
)
```

`collect` returns each provider paired with what it reported, so a component
takes one value. The squircles' colours can be changed per level — `normal`,
`warning`, `critical`, `activity`, `unknown`, `error` — with `colors` in
`agent-usage.json`, the same way as for [github-actions](#github-actions1mpy).
Argument order is the order of the squircles and of the dropdown sections.

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

## [github-actions.1m.py](plugins/github-actions.1m.py)

The latest GitHub Actions runs across your repos: one squircle per run, newest
first — amber while queued or running, green for success, red for a failure,
grey when cancelled or skipped. The runs of one commit sit side by side with a
thin line between commits, so the bar below (■ standing for a squircle in the
[image](#squircles)) is three pushes.

The dropdown has the same groups in the same order: one per commit, newest
first across every repo, with a separator where the menu bar has its line, so
the first groups are the bar's squircles one for one, and the ones after them
that the bar leaves out sit in a "More (7)" submenu below. Each commit is headed by
a squircle, its repo's name and, in grey, its short hash, branch and the
message's first line. Its submenu has the full hash, branch and author, when it
was committed, the whole message (wrapped, since menus do
not wrap), a link to the commit and a row that copies its hash. Buildkite does
not report commit times, so its submenus leave that line out. The squircle is the worst of each workflow's latest run on that
commit — red if any
failed, orange if any is still running — so a failure a later run has fixed
stops counting.

```
■■ | ■■ | ■
---
■ web-app · 3f2c1ab · main · Add a retry to the upload client | ansi=true image=… font=Menlo length=70 href=...
--3f2c1ab5e0d94c7a8b61f2e3d4c5b6a7980e1f2d | font=Menlo
--main · Octo Cat | font=Menlo
--Committed 14m ago · Fri 25 Sep 11:46 | font=Menlo
-----
--Add a retry to the upload client | font=Menlo
-----
--Uploads over a flaky connection failed on the first dropped packet. | font=Menlo
-----
--Open commit | href=https://github.com/acme/web-app/commit/3f2c1ab...
--Copy hash | bash=/usr/bin/osascript param1=-e ... terminal=false refresh=false
■ Code scanning #58 · 10m ago | href=https://github.com/acme/web-app/actions/runs/1002 image=… font=Menlo length=70
■ CI #70 · running 13m | href=https://github.com/acme/web-app/actions/runs/1001 image=… font=Menlo length=70
--push by octocat | font=Menlo
--In progress for 13m | font=Menlo
-----
--Open run | href=https://github.com/acme/web-app/actions/runs/1001
--Open workflow | href=https://github.com/acme/web-app/actions/workflows/ci.yml
---
■ web-app · 9e41d07 · main · Drop the unused settings page | ansi=true image=… font=Menlo length=70 href=...
...
---
■ api · 5d20c4e · main · Log slow queries | ansi=true image=… font=Menlo length=70 href=...
---
More (7) | font=Menlo
--■ api · 8b3e901 · main · Pin the Postgres version | ansi=true image=… font=Menlo length=70 href=...
--...
---
Refresh | refresh=true
```

GitHub has no endpoint that lists runs across repos, so it takes two steps
through `gh api`: `user/repos?sort=pushed` finds the ten repos you can access
with the most recent pushes, then each one's `actions/runs` is fetched in
parallel. The three newest commits get squircles in the menu bar and the ten
newest are listed, each with every one of its runs. Runs
are grouped by commit hash rather than by start time, which would split one
push across a window boundary. A repo that errors (SSO not authorised, say) is
listed with the error rather than hiding the rest.

Which repos you watch is personal, so it is configured outside the repo, in
`~/.config/swiftbar-plugins/github-actions.json`. Every key is optional:

```json
{
  "exclude": ["acme/legacy-app"],
  "actor": "@me"
}
```

`repos` watches a fixed list instead of discovering, `exclude` leaves repos out
by `owner/name`, `actor` shows only one person's runs (`@me` for yours), and
`squares`, `listed` and `discover` change the counts. `colors` sets the
squircle for each state — `running`, `success`, `failure`, `other` — as
`"#rrggbb"`, a 256-colour number or a name such as `"warning"`:

```json
{ "colors": { "running": "#ff9500" } }
```

A failed run shows why, without opening a browser:

```
--✗ test › Run tests | ansi=true font=Menlo href=https://github.com/acme/web-app/actions/runs/1003/job/2001
--│ ✖ 1 test failed | font=Menlo size=11 length=100
--│ expected 2 to equal 3 | font=Menlo size=11 length=100
--│ Process completed with exit code 1. | font=Menlo size=11 length=100
--Show failed log in Terminal | bash=/opt/homebrew/bin/gh param1=run param2=view ... terminal=true
```

The lines are the last ten before the job log's first `##[error]`, with the
folded groups left out as GitHub's own log view does. They come from the log
rather than from check-run annotations because a fine-grained token often
cannot read annotations. A finished run's log never changes, so each failed run
attempt is read once and kept in `failures.json` in the plugin's cache
directory.

Everything but the settings and the menu lives in `ci/`, shared with
[buildkite](#buildkite5mpy): the run model, the failure cache, and every menu
component.

---

## [buildkite.5m.py](plugins/buildkite.5m.py)

The same menu for Buildkite builds, every five minutes: squircles in the bar,
and one group per commit in the same order in the dropdown, with a failed
build's job, exit status and log tail.

```
■ | ■ | ■
---
■ web-app · 3f2c1ab · main · Add a retry to the upload client | ansi=true image=… font=Menlo length=70 href=...
--3f2c1ab5e0d94c7a8b61f2e3d4c5b6a7980e1f2d | font=Menlo
--main · Octo Cat | font=Menlo
--Committed 14m ago · Fri 25 Sep 11:46 | font=Menlo
-----
--Add a retry to the upload client | font=Menlo
-----
--Uploads over a flaky connection failed on the first dropped packet. | font=Menlo
-----
--Open commit | href=https://github.com/acme/web-app/commit/3f2c1ab...
■ Web app #7 · 12m ago | href=https://buildkite.com/acme/web-app/builds/7 image=… font=Menlo length=70
--webhook by Octo Cat | font=Menlo
--Failed in 5m | font=Menlo
-----
--✗ Test › exit 1 | ansi=true font=Menlo href=https://buildkite.com/acme/web-app/builds/7#...
--│ expected 2 to equal 3 | font=Menlo size=11 length=100
--│ 🚨 Error: The command exited with status 1 | font=Menlo size=11 length=100
-----
--Open build | href=https://buildkite.com/acme/web-app/builds/7
--Open pipeline | href=https://buildkite.com/acme/web-app
--Show failed log in Terminal | bash=/opt/homebrew/bin/bk param1=job param2=log ... terminal=true
```

It goes through [`bk`](https://buildkite.com/docs/platform/cli), the Buildkite
CLI, the way github-actions goes through `gh`. `bk auth login --scopes read_only`
signs in through the browser and keeps the token in the Keychain, and `bk api`
prefixes every path with that organisation, so the plugin never handles either.
Unlike GitHub, one call lists the builds of every pipeline.

A pipeline that builds a GitHub repo is filed under its `owner/name` and
commit, linking to both on GitHub. `repos`, `exclude`, `squares`, `listed` and
`colors` in `~/.config/swiftbar-plugins/buildkite.json` work as they do for
github-actions. A build blocked on a manual step after passing so far counts as
passed, and one still running with a job already failed counts as failed.

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

The city is `city` in [`pollen.json`](#personal-settings), in Pollenkoll's
spelling. Every pollen is one line, so reordering, renaming or dropping one is
a line:

```python
city = string_at(config.load(__file__), "city")
today = levels(city) if city else defaultdict(lambda: UNKNOWN)

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
Så många timmar och minuter kan du vistas ute i/på Sverige (Malmö)
Resten av dagen i direkt solljus
Resten av dagen i lite skugga
Resten av dagen i mycket skugga
```

`latitude`, `longitude` and `skin_type` go in
[`soltid.json`](#personal-settings). `skin_type` is the Fitzpatrick scale 1-6,
as on the agency's own form, and defaults to 1, the end that burns fastest, so
an unset one errs on the side of shorter times.

---

## [goldenhour.1h.py](plugins/goldenhour.1h.py)

This evening's golden hour.

```
🌇 18:28 - 19:18 🌇
---
Malmö, Sweden | href=https://meteogram.org/sun/sweden/malmo/
```

`city` and `country` from [`goldenhour.json`](#personal-settings), lowercased
and unaccented into the path of a meteogram.org sun page. Scraped with stdlib `html.parser`, since the site has
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
| `components` | Rows that recur: `Squircles`, `squircle`, `Meter`, `Action`, `Link`, `elbow` |
| `output` | Rendering a node tree to SwiftBar's line format, and the escaping |
| `errors` | `clean_error`, for a failure a plugin renders as a row |
| `http` | JSON/text with timeouts, parallel fetches, graceful failures |
| `data` | Reading untyped JSON without trusting its shape |
| `config` | Per-person settings in `~/.config/swiftbar-plugins/<name>.json`, outside the repo |
| `state` | Small JSON state files, written atomically, optionally owner-only |
| `jsonl_cache` | Reading append-only logs incrementally across runs |
| `shell` | Finding and running binaries despite SwiftBar's minimal `PATH` |
| `notify` | macOS notifications, with AppleScript quoting handled |
| `ansi` | Colours for menu rows: semantic names, 256-colour and hex, `rgb`, and `palette` for config overrides |
| `images` | PNGs in plain Python: squircles, warning triangles and separators |
| `meters` | Progress bars and compact number formatting |
| `dates` | Parsing the timestamp shapes APIs return |

Escaping is a large part of why the toolkit exists. SwiftBar splits a row on
its first `|`, so any text containing one silently truncates, and it splits
into rows before it parses quotes, so a newline in an attribute value forges a
whole extra row. `render` strips both from labels and attributes, keeping ESC
in labels so a coloured row still works; `escape_strict` removes that too and
is what provider-controlled text goes through.

### Squircles

The status marks in agent-usage, github-actions and buildkite are images, not
text. SwiftBar colours text only through ANSI: the basic codes are the macOS
system colours, and its 256-colour table is not xterm's — it divides without
flooring and takes blue from the wrong digit, so most codes draw some other
colour and no soft green or red is reachable at all. An `image=` has no such
limit, and gets a real rounded corner.

`images` draws them in plain Python with zlib and struct: anti-aliased from
each pixel's distance to the shape, at twice the size and marked 144 dpi so it
stays sharp on a Retina menu bar. The default colours are
GitHub's own success, attention, danger and muted shades (`SOFT_COLORS`),
which read well on a light and a dark menu bar alike.

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
