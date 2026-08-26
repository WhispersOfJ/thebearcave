# Plex

The media server. **The one service not behind Traefik** — it runs on the host network.

| | |
|---|---|
| **Image** | `plexinc/pms-docker:latest` |
| **Port** | 32400 (host network) |
| **Network** | `host` (deliberate — see below) |
| **Healthcheck** | `curl -sf http://localhost:32400/identity` |
| **Config** | `services/plex/config/` (~33 GB library, gitignored) |
| **Transcode** | `services/plex/transcode/` |
| **Depends on** | `nzbdav_rclone` healthy (restart cascade) |
| **Hardware** | `/dev/dri` (whole device, for VAAPI) |

## Why host networking

Plex's own guidance: GDM auto-discovery, DLNA, and remote-access NAT-PMP/UPnP
negotiation are all unreliable on bridge networking. Host networking also means
`localhost:32400` is shared with the host — which is how the Control Panel reaches
Plex via `host.docker.internal`.

## Volume mounts

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `services/plex/config/` | `/config` | Full library: DB, metadata, settings |
| `services/plex/transcode/` | `/transcode` | Transcode scratch space |
| `media/movies/` | `/data/movies` | Library root |
| `media/shows/` | `/data/shows` | Library root |
| `media/anime-movies/` | `/data/anime-movies` | Library root |
| `media/anime-shows/` | `/data/anime-shows` | Library root |
| `/mnt/remote/nzbdav` | `/mnt/remote/nzbdav` (rslave) | FUSE mount (symlink targets) |
| `/dev/dri` | `/dev/dri` | Hardware transcode |

## Key configuration

- `PLEX_UID` / `PLEX_GID` = **955** — matches the original native install's ownership,
  so the migrated library needed zero chown. Do not change.
- `PLEX_MEDIA_SERVER_APPLICATION_SUPPORT_DIR=/config` — flat layout, no
  `Library/Application Support` nesting (matches the migrated layout)
- `stop_grace_period: 90s` — required. Plex's shutdown legitimately takes ~40s under
  load; without this, Docker's 10s SIGKILL fires mid-shutdown and can wedge the
  container into an unkillable D-state hang
- Scheduled scanning only (`FSEventLibraryUpdatesEnabled` disabled) — new content
  appears within the scan interval or via a manual scan

## Environment variables

| Variable | Purpose |
|----------|---------|
| `PLEX_TOKEN` | API token (used by Control Panel, Metacache warm, tests) |
| `PLEX_URL` | `http://HOST_IP:32400` |

## Hardware transcoding notes

- The **whole** `/dev/dri` is mapped, not just `renderD128` — Plex's hardware-eligibility
  probe needs `card1` and the by-path entries, not just the render node
- HW transcoding covers play/decode; library scan/analysis/thumbnail passes still use CPU
- CPU limit is 12 of 16 threads, leaving desktop headroom

## Troubleshooting

- **Unkillable container (D-state)** — the 90s grace period should prevent this; if it
  happens, `docker kill` may fail too — the Control Panel's Tier-3 FUSE-abort recovery
  is the designed escape hatch
- **Everything showing deleted after a scan** — the FUSE mount was down during the scan.
  Restore the mount, restart Plex, trigger a rescan
- **Software transcode despite GPU** — check `docker exec plex ls /dev/dri` shows the
  whole device; confirm Plex Pass is active and HW acceleration is enabled
- **Plex DB lock contention** — avoid running heavy scans concurrently with WatchState
  imports and other scheduled DB writers (02:00–06:00 window)
