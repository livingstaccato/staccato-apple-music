# staccato-apple-music

Apple Music content integration for the Staccato site stack.

Initial scope: playlists only.

This repo owns:

- playlist ingestion/sync logic
- generated content contract for playlist entries
- archetype scaffolding for playlist content

This repo does not own rendering. `staccato-hugo` or the consuming site renders the generated content.

## How it reads a playlist

Open Graph, and nothing else. No Apple Developer account, no token, no key.

That is not the first choice, it is the only one that works. Apple emits full
JSON-LD for its own editorial playlists and none at all for user playlists, and
its oEmbed endpoint answers HTTP 500 for them. The Open Graph block is the one
documented surface a shared user playlist exposes, because Apple maintains it
for link previews.

The track list is deliberately not synced. It is not in the Open Graph data, and
the embed player renders it live and stays current — which a copy of three
hundred rows in a git repository would not.

## Content Contract

One file per playlist, named from the title:

```yaml
---
title: "Fun Order"
date: "2026-09-04T19:11:26Z"     # first seen, not re-stamped
playlist_url: "https://music.apple.com/us/playlist/fun-order/pl.u-Zmblzljsxk2B"
apple_music_id: "pl.u-Zmblzljsxk2B"
description: "Playlist · 300 Songs"
curator: "Tim"
track_count: 300
embed_url: "https://embed.music.apple.com/us/playlist/fun-order/pl.u-Zmblzljsxk2B"
source: "apple-music"
---
```

`artwork` is included when Apple has one. User playlists get a placeholder image
that means "no artwork", and storing it would be storing an absence, so it is
dropped.

## Configuration

All environment, so the consuming site owns its own paths:

| variable | meaning |
| -------- | ------- |
| `APPLE_MUSIC_PLAYLISTS` | newline- or comma-separated playlist URLs |
| `APPLE_MUSIC_PLAYLISTS_FILE` | a file of URLs, one per line, `#` comments allowed |
| `APPLE_MUSIC_CONTENT_DIR` | default `content/playlists` |
| `APPLE_MUSIC_STATE_FILE` | default `.apple-music-sync-state.json` |

Re-running is a no-op when nothing changed, and the date is the first time a
playlist was seen — Apple publishes none for user playlists, and inventing one
per run would reorder the section for no reason.
