# n8n

Workflow automation — glue workflows between the stack's apps and external services.

| | |
|---|---|
| **Image** | `n8nio/n8n:latest` |
| **Port** | 5678 |
| **Network** | `bearcave` |
| **Healthcheck** | `wget -qO- http://localhost:5678/healthz` |
| **Config** | `config/n8n/` (gitignored) |

## Role

- Runs workflow automations; **first workflow: Discord notifications** (import /
  grab / failure events from Radarr, Sonarr, Lidarr, nzbdav → Discord webhook)
- Media-pipeline glue workflows later (spec §10 Q2)

## Volume mounts

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `config/n8n/` | `/home/node/.n8n` | Workflows, credentials (encrypted) |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `N8N_ENCRYPTION_KEY` | Required before first start; rotation = re-encrypting all credentials |
| `N8N_BASIC_AUTH_ACTIVE` | `true` — native basic auth (no Traefik layer) |
| `N8N_BASIC_AUTH_USER` / `N8N_BASIC_AUTH_PASSWORD` | Login credentials (from `.env`) |
| `N8N_HOST` | `n8n.${HOST_IP}.nip.io` — advertised in webhook URLs |
| `N8N_PROXY_HOPS` | `1` — behind Traefik |
| `N8N_SECURE_COOKIE` | `false` in draft (Traefik terminates TLS) — flip to `true` if the client talks HTTPS end-to-end |
| `GENERIC_TIMEZONE` | From `TZ` |

## First-run

1. Open `https://n8n.HOST_IP.nip.io` — log in with the basic-auth credentials
2. `N8N_ENCRYPTION_KEY` must be set in `.env` **before first start**; generate once, keep it stable
3. Build the Discord notification workflow: webhook node triggered by
   Radarr/Sonarr/Lidarr/nzbdav events → Discord webhook

## Notes

- Runs as its own `node` user — **do not** override with PUID/PGID (data-dir
  ownership breaks)
- Credentials in n8n are encrypted with `N8N_ENCRYPTION_KEY` — back it up with
  the config dir (config-only backup scope)

## Troubleshooting

- **Webhook URLs wrong** — check `N8N_HOST`; it must match the external hostname.
- **Login rejected** — basic-auth vars must be set before first boot; recreate
  after changing them.
