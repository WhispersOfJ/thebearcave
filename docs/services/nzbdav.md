# InfiniDysk (nzbdav)

The **only downloader in the stack.** Usenet client that streams content via WebDAV —
nothing is ever written to local disk.

| | |
|---|---|
| **Image** | `ghcr.io/infinidysk/infinidysk:latest` |
| **Port** | 3000 |
| **Network** | `bearcave` |
| **Healthcheck** | `curl -fsSL http://localhost:3000/healthz` |
| **Config** | `config/nzbdav/` (gitignored) |
| **Depends on** | `prowlarr` healthy |

## Role

- Downloads from Usenet (2 providers: primary + backup, 26 connections each)
- Serves everything via WebDAV (`http://nzbdav:3000/`, user/pass from `.env`)
- Exposes a **SABnzbd-compatible API** on port 3000 — this is what Radarr/Sonarr
  (and the Control Panel) treat as the download client
- Symlink import strategy: completed downloads appear as symlinks under
  `/mnt/remote/nzbdav/completed-symlinks`
- Headless-configurable via `NZBDAV_CONFIG__*` env vars — no manual Settings-UI needed

## Key environment variables

| Variable | Purpose |
|----------|---------|
| `FRONTEND_BACKEND_API_KEY` | Web UI auth + SABnzbd API key (shared, deliberate) |
| `NZBDAV_WEBDAV_USER/PASS` | WebDAV credentials (rclone mounts with these) |
| `NZBDAV_USENET_HOST/PORT/USER/PASS` | Primary Usenet provider |
| `NZBDAV_USENET_BACKUP_*` | Backup provider |
| `NZBDAV_RCLONE_RC_PASS` | Password for the rclone RC API (`:5572`) |
| `NZBDAV_PROFILE_TOKEN` | Bearer token for InfiniDysk's own search profiles |
| `RADARR_API_KEY` / `SONARR_API_KEY` | Arr instances for import health + repair |
| `PROWLARR_API_KEY` | Indexer pull-sync (every 60 min) |

## Notable tunables (already set in compose)

| Setting | Value | Why |
|---------|-------|-----|
| Queue workers | 6 | Concurrent Radarr+Sonarr imports |
| Segment cache | 20 GB | Rewind/reseek without re-fetching from Usenet |
| NNTP pipelining | depth 8 | Batches first-segment BODY requests |
| In-flight article budget | 2048 MB | Prevents OOM crash-loops under concurrent streams |
| Repair | enabled, auto-remove off | Segment-decay detection without force-deletes |
| Watchdog / Preflight / Watchtower | enabled | Playback failover + warm-up + list pre-resolve |

## First-run

1. Open `https://nzbdav.HOST_IP.nip.io` (or `http://HOST_IP:3000`)
2. Settings → Usenet → verify providers are loaded (they come from env)
3. Confirm WebDAV works: `rclone lsd nzbdav:` from any host with the rclone.conf
4. No manual API-key setup needed — `NZBDAV_CONFIG__*` env vars are authoritative

## Troubleshooting

- **Crash-looping (OOM)** — check `docker stats nzbdav`; if it exceeds the container's
  RAM, reduce `IN_FLIGHT_ARTICLE_BUDGET_MB` or pipelining depth
- **Streaming slow on rewind/seek** — segment cache should be populated; check
  `/config` disk free (cache is capped at 20 GB)
- **Queue not persistent** — confirm the queue is empty before touching the container;
  a recreate wipes queued NZBs and silently blocklists items
- **WebDAV unreachable** — `docker compose logs nzbdav | grep -i webdav`; credentials
  come from `NZBDAV_WEBDAV_USER/PASS`
