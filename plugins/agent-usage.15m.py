#!/usr/bin/env -S /opt/homebrew/bin/uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
# <swiftbar.title>Agent usage</swiftbar.title>
# <swiftbar.author>nikteg</swiftbar.author>
# <swiftbar.author.github>nikteg</swiftbar.author.github>
# <swiftbar.desc>Coding agent subscription quotas and local spend</swiftbar.desc>
# <swiftbar.dependencies>uv</swiftbar.dependencies>
"""Coding agent subscription quotas and local spend.

Shows
    Menu bar: one circle per provider, coloured by the worst quota it reports
    — green under 75% used, yellow under 90%, red above, grey when unknown.
    Dropdown: per provider, the plan, each quota window with a bar and its
    reset time, and local activity measured from session transcripts.

Configure
    Edit the run() call at the bottom of this file. Argument order is the
    order of the circles and of the dropdown sections, so reordering or
    dropping a provider is a one-line change.
      claude(profile)      One Claude profile. No argument uses ~/.claude.
                           Pass a ClaudeProfile for a second account; the id
                           comes from the name and only has to be unique here.
      codex(monthly_cycle_day=N)
                           N is a fallback for when the API reports no reset
                           date, without which the monthly figure is labelled
                           Rolling 30-day.
      kimi(), deepseek()   No configuration.
      show_clear_cache     Adds a dropdown action that deletes the usage
                           caches, for when a transcript scan goes wrong.

Credentials
    Read-only, from where each agent already stores them: the Claude Code
    Keychain entry, Codex and Kimi auth files, and the Pi auth file for
    DeepSeek. Nothing is written back except a refreshed OAuth token.

Implementation
    lib/agent_usage/, which is a package rather than one file because it
    carries a provider registry, a pricing catalogue and a transcript cache.

Refresh
    Every 15 minutes, from the ``15m`` in this file's name.
"""

import os
import sys
from pathlib import Path

# Resolve through the symlink SwiftBar invokes, so the toolkit is found in the
# checkout this file lives in rather than in the plugin directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from agent_usage import ClaudeProfile, claude, codex, deepseek, run  # noqa: E402

HOME = os.environ.get("HOME", "")

if __name__ == "__main__":
    raise SystemExit(
        run(
            claude(
                ClaudeProfile(
                    name="Claude Default",
                    config_dir=f"{HOME}/.claude",
                    is_default=True,
                    login_hint="run claude auth login",
                    desktop_data_dir=f"{HOME}/Library/Application Support/Claude",
                )
            ),
            claude(
                ClaudeProfile(
                    name="Claude Personal",
                    config_dir=f"{HOME}/.pclaude",
                    is_default=False,
                    login_hint="run CLAUDE_CONFIG_DIR=~/.pclaude claude auth login",
                    desktop_data_dir=(
                        f"{HOME}/Library/Application Support/Claude-Personal"
                    ),
                )
            ),
            codex(),
            deepseek(),
            show_clear_cache=True,
        )
    )
