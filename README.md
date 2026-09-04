# staccato-apple-music

Apple Music content integration for the Staccato site stack.

Initial scope: playlists only.

This repo owns:

- playlist ingestion/sync logic
- generated content contract for playlist entries
- archetype scaffolding for playlist content

This repo does not own rendering. `staccato-hugo` or the consuming site renders the generated content.

## How it reads a playlist

Two sources on the playlist page, neither requiring an Apple Developer account,
a token or a key:

- **Open Graph tags** give the title, curator, canonical URL and track count.
  Apple maintains them for link previews, so they are stable.
- **Apple's serialized server data** gives the tracks: title, artist, composer
  and duration.

Apple publishes JSON-LD only for its own editorial playlists, and its oEmbed
endpoint answers HTTP 500 for user playlists, so neither is available here.

The serialized data is internal and undocumented, so nothing hardcodes a path
into it: the reader takes the longest array whose every object carries a title,
an artist and a duration. An empty result is valid — the page keeps its title
and its link, and a playlist rendering without its tracks beats a sync that
fails.

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
