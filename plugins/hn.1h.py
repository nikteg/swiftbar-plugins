#!/usr/bin/env -S /opt/homebrew/bin/uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
# <swiftbar.title>Hacker News popular posts</swiftbar.title>
# <swiftbar.author>nikteg</swiftbar.author>
# <swiftbar.author.github>nikteg</swiftbar.author.github>
# <swiftbar.desc>Tracks HN posts over a score threshold</swiftbar.desc>
# <swiftbar.dependencies>uv</swiftbar.dependencies>
"""Hacker News posts over a score threshold, with a notification on arrival.

Shows
    Menu bar: HN and the number of posts currently in the window.
    Dropdown: each post, worst-to-best by score, linking to the article. Each
    has a submenu with the comments link and how long it stays listed.

Notifies
    Once per post, the first run it crosses the threshold. A cold start can
    match dozens at once, so past NOTIFY_MAX_TITLES they are summarised into a
    single banner instead of a burst.

Configure
    Edit the call at the bottom of this file.
      min_score      Points a post needs before it is tracked.
      display_hours  How long a post stays in the dropdown after it is found.
      cleanup_days   How long it stays in the state file, which is what stops
                     an old post being re-notified if it resurfaces.
      check_limit    How far down the top-stories list to look each run.

State
    ~/Library/Caches/swiftbar-plugins/hn/posts.json, written atomically. Delete
    it to forget every post; they will be re-notified on the next run.

Source
    The public Firebase HN API. Item lookups run in parallel, and one that
    fails is skipped rather than failing the run.

Refresh
    Hourly, from the ``1h`` in this file's name. Rename to change it.
"""

import time

from sources import hackernews
from swiftbar.output import render
from swiftbar.plugin import guard
from swiftbar.ui import Item, Node, Refresh, Separator, Title


def Post(post: hackernews.Post, display_hours: int, now: float) -> Node:
    return Item(
        f"🔥 {post.score} - {post.title}",
        Item("💬 View HN comments", href=post.comments_url),
        Item(f"⏱️ {post.hours_left(display_hours, now):.0f}h left"),
        href=post.url,
        length=60,
    )


def Empty(min_score: int) -> Node:
    return [
        Item("No popular posts yet"),
        Item(f"(waiting for posts with {min_score}+ points)"),
    ]


def HackerNews(
    min_score: int, display_hours: int, cleanup_days: int, check_limit: int
) -> Node:
    posts = hackernews.popular(min_score, display_hours, cleanup_days, check_limit)
    now = time.time()

    return [
        Title(f"HN ({len(posts)})" if posts else "HN"),
        [Post(post, display_hours, now) for post in posts] or Empty(min_score),
        Separator(),
        Refresh(),
    ]


if __name__ == "__main__":
    guard(name="HN", icon="⚠️")
    print(
        render(
            HackerNews(min_score=700, display_hours=12, cleanup_days=7, check_limit=50)
        )
    )
