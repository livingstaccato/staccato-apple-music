#!/usr/bin/env python3
"""Sync public Apple Music playlists into Hugo content.

Reads the Open Graph tags Apple publishes on a playlist page and writes one
content file per playlist. No Apple Developer account, no token, no key.

Why Open Graph and not something richer: Apple emits full JSON-LD for its own
editorial playlists and none at all for user playlists, and its oEmbed endpoint
returns HTTP 500 for them. The only documented, stable surface a shared user
playlist exposes is the Open Graph block Apple maintains for link previews. The
track list is not in it — that is what the embed player is for, and the player
stays current on its own, which a synced copy of 300 rows would not.

Configuration, all environment:

  APPLE_MUSIC_PLAYLISTS       newline- or comma-separated playlist URLs
  APPLE_MUSIC_PLAYLISTS_FILE  a file of URLs, one per line, # comments allowed
  APPLE_MUSIC_CONTENT_DIR     default content/playlists
  APPLE_MUSIC_STATE_FILE      default .apple-music-sync-state.json
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTENT_DIR = Path(os.environ.get("APPLE_MUSIC_CONTENT_DIR", "content/playlists"))
STATE_FILE = Path(os.environ.get("APPLE_MUSIC_STATE_FILE", ".apple-music-sync-state.json"))

# Apple serves this when a playlist has no artwork of its own, which is every
# user playlist. Storing it would be storing the absence of a picture.
PLACEHOLDER_ARTWORK = "https://music.apple.com/assets/meta/apple-music-60.png"

USER_AGENT = "staccato-apple-music (+https://github.com/livingstaccato/staccato-apple-music)"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("apple-music")


def playlist_urls() -> list[str]:
    """Every configured playlist URL, from the file and the variable both."""
    raw: list[str] = []
    inline = os.environ.get("APPLE_MUSIC_PLAYLISTS", "")
    raw.extend(re.split(r"[\n,]", inline))

    path = os.environ.get("APPLE_MUSIC_PLAYLISTS_FILE")
    if path and Path(path).exists():
        raw.extend(Path(path).read_text(encoding="utf-8").splitlines())

    urls = []
    for line in raw:
        line = line.split("#", 1)[0].strip()
        if line:
            urls.append(line)
    return urls


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - https only, checked below
        return resp.read().decode("utf-8", errors="replace")


def open_graph(page: str) -> dict[str, str]:
    """Every og: and music: meta tag on the page, unescaped."""
    found = {}
    for prop, content in re.findall(
        r'<meta\s+property="((?:og|music):[^"]+)"\s+content="([^"]*)"', page
    ):
        found[prop] = html.unescape(content)
    return found


def playlist_id(url: str) -> str:
    """The pl.* identifier from a playlist URL."""
    m = re.search(r"/(pl\.[A-Za-z0-9_-]+)", url)
    return m.group(1) if m else ""


def embed_url(url: str) -> str:
    """Apple's official embeddable player for the same playlist."""
    return url.replace("https://music.apple.com/", "https://embed.music.apple.com/", 1)


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[\s_-]+", "-", value).strip("-") or "playlist"


def parse(url: str, page: str) -> dict[str, Any] | None:
    """One playlist's fields, or None when the page is not a playlist."""
    og = open_graph(page)
    if og.get("og:type") != "music.playlist":
        log.warning("  not a playlist page, skipped: %s", url)
        return None

    # "Fun Order by Tim on Apple Music" -> title, curator
    raw_title = re.sub(r"\s+on Apple Music$", "", og.get("og:title", ""))
    curator = ""
    m = re.match(r"^(.*?) by (.+)$", raw_title)
    if m:
        raw_title, curator = m.group(1), m.group(2)

    artwork = og.get("og:image", "")
    if artwork == PLACEHOLDER_ARTWORK:
        artwork = ""

    return {
        "title": raw_title,
        "playlist_url": og.get("og:url", url),
        "apple_music_id": playlist_id(url),
        "description": og.get("og:description", ""),
        "curator": curator,
        "artwork": artwork,
        "track_count": int(og.get("music:song_count", 0) or 0),
        "embed_url": embed_url(og.get("og:url", url)),
        "source": "apple-music",
    }


def frontmatter(entry: dict[str, Any], date: str) -> str:
    ordered = {"title": entry["title"], "date": date}
    for k in ("playlist_url", "apple_music_id", "description", "curator",
              "artwork", "track_count", "embed_url", "source"):
        if entry[k] != "" and entry[k] != 0:
            ordered[k] = entry[k]

    lines = ["---"]
    for k, v in ordered.items():
        if isinstance(v, int):
            lines.append(f"{k}: {v}")
        else:
            lines.append(f'{k}: "{str(v).replace(chr(34), chr(92) + chr(34))}"')
    lines.append("---")
    return "\n".join(lines) + "\n"


def load_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("state file unreadable, treating every playlist as new")
    return {}


def main() -> int:
    urls = playlist_urls()
    if not urls:
        log.error(
            "No playlists configured. Set APPLE_MUSIC_PLAYLISTS or "
            "APPLE_MUSIC_PLAYLISTS_FILE."
        )
        return 1

    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    added = updated = 0
    for url in urls:
        if not url.startswith("https://"):
            log.warning("  not https, skipped: %s", url)
            continue
        try:
            page = fetch(url)
        except (urllib.error.URLError, TimeoutError) as err:
            log.warning("  could not fetch %s: %s", url, err)
            continue

        entry = parse(url, page)
        if entry is None:
            continue

        pid = entry["apple_music_id"] or slugify(entry["title"])
        target = CONTENT_DIR / f"{slugify(entry['title'])}.md"
        # The date is when this playlist was first seen. Apple does not publish
        # one for user playlists, and inventing a new one on every run would
        # reorder the section for no reason.
        first_seen = state.get(pid, {}).get("date", now)
        body = frontmatter(entry, first_seen)

        if target.exists() and target.read_text(encoding="utf-8") == body:
            state[pid] = {"date": first_seen, "path": str(target)}
            continue

        was = target.exists()
        target.write_text(body, encoding="utf-8")
        state[pid] = {"date": first_seen, "path": str(target)}
        log.info("  %s: %s", "Updated" if was else "Added", target)
        updated += was
        added += not was

    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log.info("Sync complete: %d added, %d updated", added, updated)
    return 0


if __name__ == "__main__":
    sys.exit(main())
