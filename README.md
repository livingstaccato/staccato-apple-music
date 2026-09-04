# staccato-apple-music

Apple Music content integration for the Staccato site stack.

Initial scope: playlists only.

This repo owns:

- playlist ingestion/sync logic
- generated content contract for playlist entries
- archetype scaffolding for playlist content

This repo does not own rendering. `staccato-hugo` or the consuming site renders the generated content.

## Planned Content Contract

Generated playlist entries should include stable fields for:

- `title`
- `date`
- `playlist_url`
- `apple_music_id`
- `description`
- `artwork`
- `curator`
- `tracks`
- `source`
