# Bazarr

Subtitle management — fetches and places subtitles for the existing movie and TV libraries.

| | |
|---|---|
| **Image** | `ghcr.io/hotio/bazarr:release` |
| **Port** | 6767 |
| **Network** | `bearcave` |
| **Healthcheck** | `curl -sf http://localhost:6767/api/health` |
| **Config** | `config/bazarr/` (gitignored) |
| **Depends on** | `nzbdav_rclone` healthy (restart cascade) |

## Role

- Connects to Radarr and Sonarr to discover library items
- Fetches subtitles directly from subtitle providers (no nzbdav category needed)
- Places subtitle files into the media folders next to the video

## Volume mounts

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `config/bazarr/` | `/config` | App state |
| `/mnt/remote/nzbdav` | `/mnt/remote/nzbdav` (rslave) | FUSE mount |
| `media/movies/` | `/data/movies` | Movie root folder |
| `media/shows/` | `/data/shows` | TV root folder |
| `media/anime-movies/` | `/data/anime-movies` | Anime movie root folder |
| `media/anime-shows/` | `/data/anime-shows` | Anime TV root folder |

## Environment variables

None — Bazarr reads Radarr/Sonarr API keys from its own UI configuration.

## First-run

1. Open `https://bazarr.HOST_IP.nip.io`
2. Settings → Radarr: URL `http://radarr:7878`, API key = `RADARR_API_KEY` from `.env`
3. Settings → Sonarr: URL `http://sonarr:8989`, API key = `SONARR_API_KEY` from `.env`
4. Point Bazarr at the same media paths as Radarr/Sonarr (`/data/...`)
5. Add a subtitle provider (e.g. OpenSubtitles) and enable auto-search

## Notes

- Bazarr is a **pure add-on** — no nzbdav category change or Prowlarr registration needed
- Subtitle placement requires write access to the media folders the same way the *arrs import

## Troubleshooting

- **Subtitles not placed** — check Bazarr's log for path/permission errors; the
  container mounts the same media roots as Radarr/Sonarr.
- **Provider auth errors** — re-check the provider credentials in Settings.
