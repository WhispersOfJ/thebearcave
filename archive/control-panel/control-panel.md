# Control Panel

Django + htmx infrastructure dashboard — the operations surface for the stack.

| | |
|---|---|
| **Source** | `services/control-panel/django/` (Python 3.14, Django 5.2) |
| **Build** | `docker compose build control-panel` |
| **Port** | 8420 |
| **Network** | `bearcave` |
| **Healthcheck** | `python3 /app/healthcheck.py` |
| **Data** | `data/control-panel/` (SQLite DB) |
| **Logs** | `logs/control-panel/` (rotating) |
| **Privileges** | `pid: host`, docker.sock, `/proc`, `/sys/fs/fuse` |

## Role

- Container lifecycle: status, start/stop/restart, live log streaming (SSE)
- Host operations: resources, disk health, OOM checks, mount health, perms
- NzbDAV queue management: history, stats, delete failures
- WatchState status/history/import, Cleanuparr instances/strikes
- Aggregate queue status across Radarr + Sonarr + NzbDAV
- Poster sync, ratings (IMDb/MDBList), TMDb lookups

## API surface

Full reference in [AGENTS.md](../../AGENTS.md#control-panel-api-8420apiv2). Highlights:

```
GET  /api/v2/host/status          POST /api/v2/host/container/<n>/restart
GET  /api/v2/host/containers      GET  /api/v2/nzbdav/queue
GET  /api/v2/host/mount-health    GET  /api/v2/queue/status
POST /api/v2/host/reboot          POST /api/v2/host/pacman-upgrade   (bearer auth)
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `PLEX_URL` / `PLEX_TOKEN` | Plex API access (via host.docker.internal) |
| `RADARR_API_KEY` / `SONARR_API_KEY` / `PROWLARR_API_KEY` | Arr API access |
| `FRONTEND_BACKEND_API_KEY` | NzbDAV API access |
| `CONTROL_PANEL_SECRET_KEY` | Session-cookie signing |
| `CONTROL_PANEL_ADMIN_USERNAME/PASSWORD` | Bootstrap admin |
| `CONTROL_PANEL_SERVICE_API_KEY` | Service-to-service auth for stack-* commands |
| `CONTROL_PANEL_SECURE_COOKIE` | Set only behind TLS (breaks login over plain HTTP) |
| `TMDB_KEY` / `FANART_KEY` / `TVDB_KEY` / `OMDB_KEY` / `MDBLIST_KEY` | Poster/ratings lookups |
| `DISCORD_WEBHOOK_URL` | Notification test |
| `HOST_IP` | Origin/Host validation |

## Privilege model

The container has elevated access on purpose — read the rationale in the compose file
comments before changing it:

| Privilege | Enables |
|-----------|---------|
| `pid: host` | Plex D-state thread scan, host resources |
| docker.sock | Container start/stop/restart |
| `/sys/fs/fuse` (writable) | Force Unstick — abort a wedged FUSE connection |
| `/proc` | D-state introspection |

> **Security tradeoff:** this is an unauthenticated LAN service with elevated blast
> radius, mitigated by Origin/Host validation. Keep it LAN-only.

## Troubleshooting

- **Env changes not applied** — Control Panel reads `.env` at create time.
  Use `--force-recreate`, not `restart`
- **Time fields wrong** — TZ is set; if it regresses, container lost its env
- **Login fails over HTTPS** — `CONTROL_PANEL_SECURE_COOKIE` is set without real TLS
  in front, or unset with TLS in front. Keep it empty on plain LAN
- **`/api/version` stale** — the README is bind-mounted as a single file; editors that
  replace the file leave the mount stale. Recreate the container
