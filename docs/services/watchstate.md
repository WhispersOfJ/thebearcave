# WatchState

Plex watch-state sync/backup — keeps its own record of what has been watched,
fed from Plex by a scheduled import plus a webhook.

| | |
|---|---|
| **Image** | `ghcr.io/arabcoders/watchstate:latest` |
| **Port** | 8705 (host) → 8080 (container) |
| **Network** | `bearcave` |
| **Healthcheck** | `curl -sf -H "X-apikey: $WS_API_KEY" http://localhost:8080/v1/api/system/healthcheck` |
| **Config** | `config/watchstate/` (gitignored) |
| **User** | `${PUID}:${PGID}` (image is rootless — the `user:` line is load-bearing) |

## Role

- Scheduled import of Plex watch history + a Plex webhook for real-time events
- Protects watch history from Plex DB loss

## Environment variables

| Variable | Purpose |
|----------|---------|
| `WS_API_KEY` | Authenticates every `/v1/api` call (`X-apikey` header) |
| `WS_SYSTEM_SECRET` | Signs WatchState's internal tokens |
| `WS_CRON_IMPORT` | `true` — keep scheduled import enabled even with webhooks (webhooks drop events) |
| `WS_CRON_IMPORT_AT` | `25 0-1,6-23 * * *` — skips 02:00–05:59 (SQLite write-contention window) |
| `WS_CRON_EXPORT` | `false` — export would write watch state back INTO Plex |

## Hard rules (from the compose comments)

1. **Keep the scheduled import AND the webhook.** Upstream says to keep both — webhooks
   drop events. Do not "optimize" one away.
2. **`WS_SECURE_API_ENDPOINTS=true` is mandatory.** Without it the whole `/v1/api`
   surface is unauthenticated, including token-issuing endpoints.
3. **Don't enable export.** Plex is the only backend; there's nothing to write back to,
   and an accidental export mass-writes the same DB the import window protects.

## Troubleshooting

- **Healthcheck fails** — the healthcheck hits the API endpoint (not the WebUI "/",
  which answers 200 with a dead backend). Check `WS_API_KEY` matches
- **Import times look wrong** — TZ must be set (`WS_TZ`)
