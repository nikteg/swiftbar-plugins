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
from dataclasses import dataclass

from swiftbar_lib import state
from swiftbar_lib.http import gather, get_json, quiet
from swiftbar_lib.notify import notify
from swiftbar_lib.output import show
from swiftbar_lib.plugin import guard
from swiftbar_lib.ui import Item, Node, Refresh, Separator, Title

PLUGIN = "hn"
STATE_FILE = "posts.json"
API_BASE = "https://hacker-news.firebaseio.com/v0"

SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86_400

#: One banner per post is fine for a handful, but a cold start can match
#: dozens; past this they are summarised into a single notification.
NOTIFY_MAX_TITLES = 3


@dataclass(frozen=True)
class Post:
    id: int
    title: str
    score: int
    url: str
    comments_url: str
    fetched_at: float

    def hours_left(self, display_hours: int, now: float) -> float:
        return display_hours - (now - self.fetched_at) / SECONDS_PER_HOUR


def comments_url(story_id: int) -> str:
    return f"https://news.ycombinator.com/item?id={story_id}"


def _decode(stored: dict) -> Post:
    return Post(
        id=stored["id"],
        title=stored["title"],
        score=stored["score"],
        url=stored["url"],
        comments_url=stored["hn_url"],
        fetched_at=stored["fetched_at"],
    )


def _fresh(stored: dict, max_age_seconds: float) -> dict:
    now = time.time()

    return {
        key: post
        for key, post in stored.items()
        if now - post.get("fetched_at", 0) < max_age_seconds
    }


def _collect(stored: dict, min_score: int, check_limit: int) -> list[Post]:
    """Records top stories newly over the threshold, and returns just those."""
    top = get_json(f"{API_BASE}/topstories.json") or []
    unseen = [sid for sid in top[:check_limit] if str(sid) not in stored]
    items = gather(
        unseen,
        lambda sid: quiet(lambda: get_json(f"{API_BASE}/item/{sid}.json"), None),
    )

    now = time.time()
    added = []

    for item in items:
        if not item or item.get("score", 0) < min_score:
            continue

        # Ask HN and similar have no URL of their own; point those at the thread.
        stored[str(item["id"])] = {
            "id": item["id"],
            "title": item.get("title", "Untitled"),
            "url": item.get("url") or comments_url(item["id"]),
            "hn_url": comments_url(item["id"]),
            "score": item["score"],
            "fetched_at": now,
        }
        added.append(_decode(stored[str(item["id"])]))

    return added


def _announce(added: list[Post]) -> None:
    ranked = sorted(added, key=lambda post: -post.score)

    if len(ranked) <= NOTIFY_MAX_TITLES:
        for post in ranked:
            notify(f"HN: {post.title[:50]}", f"🔥 {post.score} points")

        return

    titles = " • ".join(post.title[:50] for post in ranked[:NOTIFY_MAX_TITLES])
    notify(f"HN: {len(ranked)} new popular posts", titles)


def popular(
    min_score: int, display_hours: int, cleanup_days: int, check_limit: int
) -> list[Post]:
    """Refreshes, notifies about new posts, and returns what to show.

    Posts stay in state for ``cleanup_days`` but leave the menu after
    ``display_hours``; the gap is what stops an old post being re-notified if
    it resurfaces in the top list.
    """
    stored = _fresh(state.load(PLUGIN, STATE_FILE), cleanup_days * SECONDS_PER_DAY)
    added = _collect(stored, min_score, check_limit)

    if added:
        _announce(added)

    state.save(PLUGIN, stored, STATE_FILE)

    visible = _fresh(stored, display_hours * SECONDS_PER_HOUR).values()

    return sorted((_decode(post) for post in visible), key=lambda post: -post.score)


def Story(post: Post, display_hours: int, now: float) -> Node:
    """One story, with its comments link and remaining time in a submenu."""
    return Item(
        f"🔥 {post.score} - {post.title}",
        Item("💬 View HN comments", href=post.comments_url),
        Item(f"⏱️ {post.hours_left(display_hours, now):.0f}h left"),
        href=post.url,
        length=60,
    )


if __name__ == "__main__":
    guard(name="HN", icon="⚠️")

    min_score = 700
    display_hours = 12

    posts = popular(
        min_score=min_score, display_hours=display_hours, cleanup_days=7, check_limit=50
    )
    now = time.time()

    show(
        Title(f"HN ({len(posts)})" if posts else "HN"),
        [Story(post, display_hours, now) for post in posts]
        or [
            Item("No popular posts yet"),
            Item(f"(waiting for posts with {min_score}+ points)"),
        ],
        Separator(),
        Refresh(),
    )
