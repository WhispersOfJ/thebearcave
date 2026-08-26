# Sonarr

TV show management — tracks close to 300,000 episode records across the library.

| | |
|---|---|
| **Image** | `ghcr.io/hotio/sonarr:release` |
| **Port** | 8989 |
| **Network** | `bearcave` |
| **Healthcheck** | `curl -sf http://localhost:8989/ping` |
| **Config** | `services/sonarr/config/` (gitignored) |
| **Depends on** | `nzbdav_rclone` healthy (restart cascade) |

## Role

- Tracks the TV library, including anime (folded in via genre/tag routing)
- Searches via Prowlarr, grabs through InfiniDysk
- Imports via symlinks into the FUSE mount

## Volume mounts

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `services/sonarr/config/` | `/config` | App state |
| `/mnt/remote/nzbdav` | `/mnt/remote/nzbdav` (rslave) | FUSE mount |
| `media/shows/` | `/data/shows` | TV root folder |
| `media/anime-shows/` | `/data/anime-shows` | Anime TV root folder |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `SONARR_API_KEY` | API key (generated on first boot, copy into `.env`) |

## First-run

Mirror Radarr's steps (see [radarr.md](radarr.md)) with `/data/shows` and
`/data/anime-shows` as root folders.

## Notes

- Episode structure is large — scans can be slow; scheduled scanning is the norm
- Missing-aired entries are a known gap for shows with irregular air dates
