# Audiobookshelf

Audiobook and podcast server — serves its own content with a built-in player (does not feed Plex).

| | |
|---|---|
| **Image** | `ghcr.io/advplyr/audiobookshelf:latest` |
| **Port** | 13378 (container 80) |
| **Network** | `bearcave` |
| **Healthcheck** | `wget -qO- http://localhost:80/` |
| **Config** | `config/audiobookshelf/` (gitignored) |
| **User** | `${PUID}:${PGID}` via `user:` (no PUID/PGID env support) |
| **CVE note** | Deploy-as-is — form-data/sequelize CVEs tracked upstream (spec §14) |

## Role

- Serves audiobooks, ebooks, and podcasts with a streaming player and progress sync
- Watches media folders and scans for new content (no *arr / download-client integration)
- **Serves its own content** — does not use Plex for playback

## Volume mounts

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `config/audiobookshelf/` | `/config` | App state + metadata DB |
| `media/audiobooks/` | `/audiobooks` | Audiobook library |
| `media/books/` | `/books` | Ebook library |
| `media/podcasts/` | `/podcasts` | Podcast library |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `TZ` | Timezone (from stack common env) |

## First-run

1. Open `https://audiobookshelf.HOST_IP.nip.io`
2. Create the admin account
3. Add library folders: `/audiobooks`, `/books`, `/podcasts`
4. Set the watch folders to auto-scan (`audiobooks`, `books`, `podcasts` categories)

## Acquisition

No *arr exists for audiobooks — manual NZB grabs into nzbdav (`audiobooks`
category) land in `/mnt/remote/nzbdav/audiobooks`, then get
imported/symlinked into `media/audiobooks/` (or the ABS watch folder scans them).
Requires the nzbdav category rollout first (see [HISTORY.md](../../HISTORY.md#the-2026-08-28-expansion) — nzbdav category rollout).

## Notes

- Metadata (cover art, thumbnails) is stored in the config dir — included in the config-only backup scope
- Deployed with `user: "${PUID}:${PGID}"` since the official image lacks PUID/PGID env vars — verify ownership at deploy
