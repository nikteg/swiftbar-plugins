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

from swiftbar import state
from swiftbar.http import gather, get_json, quiet
from swiftbar.notify import notify
from swiftbar.output import Menu
from swiftbar.plugin import run as run_plugin

PLUGIN = "hn"
API_BASE = "https://hacker-news.firebaseio.com/v0"

SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86_400

NOTIFY_MAX_TITLES = 3


def comments_url(story_id: int) -> str:
    return f"https://news.ycombinator.com/item?id={story_id}"


def story_url(item: dict) -> str:
    # Ask HN and similar have no URL of their own; point those at the thread.
    return item.get("url") or comments_url(item["id"])


def fresh(posts: dict, max_age_seconds: float) -> dict:
    now = time.time()

    return {
        key: post
        for key, post in posts.items()
        if now - post.get("fetched_at", 0) < max_age_seconds
    }


def collect(posts: dict, min_score: int, check_limit: int) -> list[dict]:
    """Records top stories newly over the threshold, and returns just those."""
    top = get_json(f"{API_BASE}/topstories.json") or []
    unseen = [sid for sid in top[:check_limit] if str(sid) not in posts]
    items = gather(
        unseen,
        lambda sid: quiet(lambda: get_json(f"{API_BASE}/item/{sid}.json"), None),
    )

    now = time.time()
    added = []

    for item in items:
        if not item or item.get("score", 0) < min_score:
            continue

        post = {
            "id": item["id"],
            "title": item.get("title", "Untitled"),
            "url": story_url(item),
            "hn_url": comments_url(item["id"]),
            "score": item["score"],
            "fetched_at": now,
        }
        posts[str(item["id"])] = post
        added.append(post)

    return added


def announce(added: list[dict]) -> None:
    ranked = sorted(added, key=lambda post: -post["score"])

    if len(ranked) <= NOTIFY_MAX_TITLES:
        for post in ranked:
            notify(
                "HN: {}".format(post["title"][:50]),
                "🔥 {} points".format(post["score"]),
            )

        return

    titles = " • ".join(post["title"][:50] for post in ranked[:NOTIFY_MAX_TITLES])
    notify(f"HN: {len(ranked)} new popular posts", titles)


def run(
    min_score: int = 700,
    display_hours: int = 12,
    cleanup_days: int = 7,
    check_limit: int = 50,
) -> int:
    def build(menu: Menu) -> None:
        posts = fresh(state.load(PLUGIN, "posts.json"), cleanup_days * SECONDS_PER_DAY)
        added = collect(posts, min_score, check_limit)

        if added:
            announce(added)

        state.save(PLUGIN, posts, "posts.json")

        visible = sorted(
            fresh(posts, display_hours * SECONDS_PER_HOUR).values(),
            key=lambda post: -post["score"],
        )
        menu.title(f"HN ({len(visible)})" if visible else "HN")
        menu.sep()

        if not visible:
            menu.item("No popular posts yet")
            menu.item(f"(waiting for posts with {min_score}+ points)")
        else:
            now = time.time()

            for post in visible:
                row = menu.item(
                    "🔥 {} - {}".format(post["score"], post["title"]),
                    href=post["url"],
                    length=60,
                )
                row.item("💬 View HN comments", href=post["hn_url"])
                left = display_hours - (now - post["fetched_at"]) / SECONDS_PER_HOUR
                row.item(f"⏱️ {left:.0f}h left")

        menu.sep()
        menu.refresh_item()

    return run_plugin(build, name="HN", icon="⚠️")


if __name__ == "__main__":
    raise SystemExit(run(min_score=700, display_hours=12))
