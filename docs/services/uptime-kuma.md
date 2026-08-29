# Uptime Kuma

Self-hosted status/uptime monitoring — monitors services and pages with a nice dashboard.

| | |
|---|---|
| **Image** | `louislam/uptime-kuma:2.5.3-slim-rootless` |
| **Port** | 3002 (container 3001) |
| **Network** | `bearcave` |
| **Healthcheck** | `wget -qO- http://localhost:3001/` |
| **Config** | `config/uptime-kuma/` (gitignored, SQLite) |
| **⚠️ Deploy gate** | **Slip-gated** — see spec §10 #10 and §14 (CVE hold) |

## Role

- Monitors the stack's services (HTTP/TCP/ping) with uptime history
- Status page + notifications on state changes
- Monitors from inside `bearcave` — reach every container by service name

## Volume mounts

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `config/uptime-kuma/` | `/app/data` | SQLite DB + config |

## Ports

| Host | Container | Purpose |
|------|-----------|---------|
| 3002 | 3001 | Web UI (3001 host taken by grafana → 3002) |

## Deploy gate (read before deploying)

**No published tag clears the trivy CRITICAL gate as of 2026-08-29:**
`:1`/`:latest` = EOL Debian 10 buster (13 C); `:2` = bookworm (134 C, worse);
`2.5.3-slim-rootless` = best (bookworm, UID 1000, ~12 C — live jsonata /
protobufjs / grpc deps that aren't ignorable under repo policy).

**Re-scan 2026-08-29 (trivy 0.74.0, DB updated 2026-08-29, same flags as CI):**
`2.5.3-slim-rootless` still fails the gate — **7 fixable CRITICAL**
(`--ignore-unfixed`, the CI gate's metric; debian 12.14, Node.js, `cloudflared`).
Still the newest published tag on Docker Hub. Still slipped — re-check each cycle.

**Action at Phase 3 kickoff:** re-scan `louislam/uptime-kuma:2.5.3-slim-rootless`;
deploy only if 0 CRITICAL, otherwise **slip Uptime Kuma to a later phase** and
re-check each cycle (tracking item: spec §10 #10).

## First-run

1. Open `https://uptime-kuma.HOST_IP.nip.io` (or `http://HOST_IP:3002`)
2. Create the admin account
3. Add monitors: each stack service by `https://<name>.HOST_IP.nip.io`
   (or `http://<service>:<port>` from inside bearcave)

## Notes

- `2.5.3-slim-rootless` runs as UID 1000 — no PUID/PGID env needed, no root
- 128m/0.25 is tight (Node + SQLite) — likely needs a Small-tier bump after 48h
