# Lidarr

Music acquisition — the music half of the *arr family, feeding the Plex music library.

| | |
|---|---|
| **Image** | `ghcr.io/hotio/lidarr:nightly` |
| **Port** | 8686 |
| **Network** | `bearcave` |
| **Healthcheck** | `curl -sf http://localhost:8686/ping` |
| **Config** | `config/lidarr/` (gitignored) |
| **Depends on** | `nzbdav_rclone` healthy (restart cascade) |
| **CVE note** | `:nightly` required — `:release` ships stale .NET 8.0.12 (CVE-2025-55315, 5 CRITICAL); see spec §14 |

## Role

- Tracks artists/albums and monitors releases for the music library
- Searches via Prowlarr, grabs through InfiniDysk's SABnzbd-compatible API
- Imports via symlinks into the FUSE mount, using the new `music` nzbdav category
- Music serves through Plex (Lidarr does not serve content itself)

## Volume mounts

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `config/lidarr/` | `/config` | App state |
| `/mnt/remote/nzbdav` | `/mnt/remote/nzbdav` (rslave) | FUSE mount for symlink imports |
| `media/music/` | `/data/music` | Music root folder |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `LIDARR_API_KEY` | API key (generated on first boot, copy into `.env`) |

## First-run

1. Open `https://lidarr.HOST_IP.nip.io`
2. Download client → Add → **InfiniDysk**: host `nzbdav`, port 3000,
   API key = `FRONTEND_BACKEND_API_KEY` from `.env`, category `music`
3. Root folder: `/data/music`
4. Copy the generated API key into `.env`, `docker compose up -d --force-recreate lidarr`
5. Indexers arrive automatically via Prowlarr push-sync

Requires the nzbdav category rollout first (see [HISTORY.md](../../HISTORY.md#the-2026-08-28-expansion) — nzbdav category rollout).

## Troubleshooting

- **Imports failing with I/O errors** — the FUSE mount may be down. Check
  `docker exec nzbdav_rclone mountpoint -q /mnt/remote/nzbdav`; restart dependents after.
- **API key changed** — every consumer reads `LIDARR_API_KEY`; update `.env` and
  `--force-recreate` the consumers.
- **Image is a dev build** — `:nightly` clears the CVE gate but is dev-grade;
  re-check `:release` each update cycle in case hotio refreshes it past .NET 8.0.21.
