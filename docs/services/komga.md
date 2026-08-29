# Komga

Comics and manga server — serves its own content with a built-in reader (does not feed Plex).

| | |
|---|---|
| **Image** | `gotson/komga:1.x` |
| **Port** | 25600 |
| **Network** | `bearcave` |
| **Healthcheck** | `wget -qO- http://localhost:25600/actuator/health \| grep -q UP` |
| **Config** | `config/komga/` (gitignored) |
| **User** | `${PUID}:${PGID}` via `user:` (no PUID/PGID env support) |
| **Image note** | `1.x` pin — passes the CVE gate with the draft `.trivyignore` entries (spec §14) |

## Role

- Serves comics/manga libraries with a web reader and reading-progress sync
- Watches library folders and scans for new content (no *arr / download-client integration)
- **Serves its own content** — does not use Plex for reading

## Volume mounts

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `config/komga/` | `/config` | App state |
| `media/comics/` | `/comics` | Comics/manga library |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `TZ` | Timezone (from stack common env) |

## First-run

1. Open `https://komga.HOST_IP.nip.io`
2. Create the admin account
3. Add library: `/comics`
4. Optional: enable the embedded OPDS feed for reading apps

## Acquisition

No *arr exists for comics — manual NZB grabs into nzbdav (`comics` category)
land in `/mnt/remote/nzbdav/comics`, then get imported/symlinked into
`media/comics/` (Komga scans the library folder). Requires the nzbdav category
rollout first (see [HISTORY.md](../../HISTORY.md#the-2026-08-28-expansion) — nzbdav category rollout).

## Notes

- 1 GiB / 1.0 CPU tier — Komga indexes + thumbnail generation is the heaviest of the Phase-1 tools; adjust after 48h
- Deployed with `user: "${PUID}:${PGID}"` since the official image lacks PUID/PGID env vars — verify ownership at deploy
