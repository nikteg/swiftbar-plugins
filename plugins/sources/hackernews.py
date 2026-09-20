"""Hacker News top stories, with the seen-post state that stops re-notifying."""

from __future__ import annotations

import time
from dataclasses import dataclass

from swiftbar import state
from swiftbar.http import gather, get_json, quiet
from swiftbar.notify import notify

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


def _comments_url(story_id: int) -> str:
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
            "url": item.get("url") or _comments_url(item["id"]),
            "hn_url": _comments_url(item["id"]),
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
    """Refreshes from the API, notifies about new posts, returns what to show.

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
