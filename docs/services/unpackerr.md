# Unpackerr

Auto-extraction of downloads — watches the *arr queue and extracts archives when done.

| | |
|---|---|
| **Image** | `golift/unpackerr` (digest-pinned) |
| **Ports** | none (no web UI) |
| **Network** | `bearcave` |
| **Healthcheck** | process-alive check via `/proc` |
| **Depends on** | `nzbdav_rclone` healthy |

## Role

- Polls Radarr/Sonarr queues for finished downloads
- Extracts archives (rar/zip/7z) before the *arr import step
- No web UI or API — configured entirely via env

## Environment variables

| Variable | Purpose |
|----------|---------|
| `UN_RADARR_0_URL` | `http://radarr:7878` |
| `UN_RADARR_0_API_KEY` | `RADARR_API_KEY` |
| `UN_SONARR_0_URL` | `http://sonarr:8989` |
| `UN_SONARR_0_API_KEY` | `SONARR_API_KEY` |

## Notes

- No `UN_READARR` entry — Bindery replaced Readarr and isn't a supported "Starr app";
  low impact since ebook releases are rarely RAR'd
- The `services/unpackerr/` volume is a plain bind (`/usenet`) — not part of the
  extraction path, kept for compatibility
- Restart cascades with the FUSE mount (`depends_on: restart: true`)
