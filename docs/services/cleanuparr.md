# Cleanuparr

Queue cleanup automation — strikes, malware blocking, stalled-cleanup.

| | |
|---|---|
| **Image** | `ghcr.io/cleanuparr/cleanuparr:2.10.5` |
| **Port** | 11011 |
| **Network** | `bearcave` |
| **Healthcheck** | `curl -sf http://localhost:11011/` |
| **Config** | `config/cleanuparr/` (gitignored) |
| **Depends on** | `nzbdav_rclone` healthy |

## Role

- Automates what the Control Panel's "unstick" button does by hand
- QueueCleaner: stalled/warning/error queue items
- MalwareBlocker: blocks releases matching malware patterns
- Needs filesystem access to the paths the download client reports — hence the FUSE
  mount bind

## First-run

Cleanuparr discovers *arr apps but needs explicit instance registration in its
`arr_instances` table (it does not auto-register). Register Radarr + Sonarr after
first boot.

## Troubleshooting

- **Not acting on the queue** — confirm instances are registered (Settings → Instances)
  and API keys match `.env`
- **Can't see download paths** — the FUSE mount bind must be present; check
  `docker exec cleanuparr ls /mnt/remote/nzbdav`

## Automated Cleanup Setup

Cleanuparr needs manual configuration through its web UI (`http://localhost:11011`).

### Steps

1. Open `http://cleanuparr:11011` (or `http://HOST_IP:11011`)
2. Add instances:
   - **Radarr**: URL `http://radarr:7878`, API key from `.env` (`RADARR_API_KEY`)
   - **Sonarr**: URL `http://sonarr:8989`, API key from `.env` (`SONARR_API_KEY`)
3. Configure cleanup rules:
   - Enable **Stale download cleanup** (remove downloads stuck >48h)
   - Enable **Failed download cleanup** (remove after 3 retry failures)
   - Enable **Orphaned file cleanup** (remove files not tracked by arr apps)
   - Set **Minimum file age** to 24h (don't clean recent downloads)
4. Enable **Strike system** (3 strikes = auto-remove)

### What Cleanuparr Does

- Monitors Radarr/Sonarr queues for stalled/failed downloads
- Removes orphaned files from the download client
- Cleans up failed releases from the queue
- Runs on a configurable schedule (default: every 30 minutes)
