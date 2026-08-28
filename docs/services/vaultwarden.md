# Vaultwarden

Self-hosted password manager — a lightweight Bitwarden-compatible server.

| | |
|---|---|
| **Image** | `vaultwarden/server:latest` |
| **Port** | 8222 (container 80) |
| **Network** | `bearcave` |
| **Healthcheck** | `wget -qO- http://localhost:80/alive` |
| **Config** | `config/vaultwarden/` (gitignored, SQLite + attachments) |

## Role

- Password/secret manager compatible with Bitwarden clients (browser extension, mobile apps)
- Native admin panel at `/admin`, guarded by `VAULTWARDEN_ADMIN_TOKEN` (native auth only — no Traefik basic-auth layer)

## Volume mounts

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `config/vaultwarden/` | `/data` | SQLite DB + attachments |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `VAULTWARDEN_ADMIN_TOKEN` | Admin-panel auth (from `.env`) |
| `SIGNUPS_ALLOWED` | `false` in the draft — flip `true` once for the first account, then back |
| `WEBSOCKET_ENABLED` | `true` — live vault sync on the same port, no extra Traefik work |

## First-run

1. Set `SIGNUPS_ALLOWED=true` in `.env`, `docker compose up -d vaultwarden`
2. Open `https://vaultwarden.HOST_IP.nip.io` (or `http://HOST_IP:8222`) and create the first account
3. Set `SIGNUPS_ALLOWED=false` (or `INVITATIONS_ALLOWED=true`), recreate
4. Log in to `/admin` with `VAULTWARDEN_ADMIN_TOKEN` and finish config
5. Point Bitwarden clients at the server URL

## Notes

- **CVE posture:** libmariadb3 present in the image but the binary has zero
  MariaDB references (SQLite backend) — covered by the draft `.trivyignore`
  entries (spec §14)
- Config-only backup scope: the `/data` dir holds the vault — make sure it's in
  the backup playbook

## Troubleshooting

- **Can't reach admin panel** — `VAULTWARDEN_ADMIN_TOKEN` must be set before
  first boot and recreated after changing it.
- **Vault sync not live** — check `WEBSOCKET_ENABLED`; websockets pass through
  Traefik on the same port.
