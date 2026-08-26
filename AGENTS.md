# AGENTS.md

Complete reference for AI coding agents working in this repo. Read `CLAUDE.md` first for
work style and non-negotiable rules — this file covers the system itself.

---

## What This Repo Is

A unified media-acquisition-and-serving stack. 22 Docker Compose services, a Django
control panel, an arr-dashboard, Prometheus/Grafana monitoring, Traefik reverse proxy,
and CI/CD via GitHub Actions. Hosted on Linux.

Merged from two repos: `media-stack` (Usenet + Plex + *arr apps) and `metacacharr`
(TMDB/TVDB metadata cache). Legacy files from both are preserved in `archive/`.

---

## Architecture

```
                    ┌──────────────────────────────┐
                    │         Traefik :80/:443      │
                    │    (reverse proxy, HTTPS)     │
                    └──────────────┬───────────────┘
                                   │ routes to everything
                                   ▼
Prowlarr (indexers) ──▶ Radarr + Sonarr ──▶ nzbdav (Usenet) ──▶ FUSE mount ──▶ Plex
                              │                                         (host network)
                    ┌─────────┴─────────┐
                    │                   │
          Control Panel :8420    arr-dashboard :41789
          (Infrastructure)       (Media Operations)
                    │                   │
              Prometheus :9090    Grafana :3001
```

### Service Categories

| Category | Services |
|----------|----------|
| **Reverse proxy** | Traefik (ports 80/443) |
| **Indexing** | Prowlarr |
| **\*arr apps** | Radarr (movies), Sonarr (TV) |
| **Usenet** | InfiniDysk/nzbdav + nzbdav_rclone sidecar |
| **Requests** | Seerr |
| **Media server** | Plex (host network, VAAPI transcoding) |
| **Metadata** | Metacache (built from source, TMDB/TVDB cache) |
| **Dashboard** | Control Panel (Django) |
| **Queue mgmt** | Unpackerr, Cleanuparr |
| **Watch state** | WatchState |
| **Logging** | Loki, Promtail, Grafana |
| **Metrics** | Prometheus, Node Exporter, cAdvisor, nzbdav-exporter |
| **ARR dashboard** | arr-dashboard |
| **Landing page** | Nginx |

### Two Dashboard Surfaces

| Panel | Port | Technology | Responsibilities |
|-------|------|------------|-----------------|
| **Control Panel** | 8420 | Django + htmx | Container lifecycle, host operations, NzbDAV, Watchstate, FUSE mounts, queue aggregation |
| **arr-dashboard** | 41789 | Next.js (Node 22) | Multi-instance queue/calendar/history, TRaSH Guides, library cleanup, auto-hunting, Plex analytics, notifications, statistics |

They share no state. Both talk independently to Radarr/Sonarr/Prowlarr APIs.

- **Content flow:** Prowlarr indexes → Radarr/Sonarr queue → nzbdav downloads → rclone FUSE mount → Plex serves
- **Metadata:** Metacache (:8765) caches TMDB/TVDB lookups locally so Plex refreshes hit cache
- **Observability:** Prometheus scrapes node-exporter, cadvisor, nzbdav-exporter, metacache. Loki ingests Docker logs via Promtail. Grafana queries both.
- **Control:** Django dashboard at :8420 for infrastructure ops. arr-dashboard at :41789 for media ops.
- **Reverse proxy:** Traefik routes all services except Plex (which uses host network) via Host-based routing with automatic HTTPS.

---

## Services (22 containers)

| # | Service | Purpose | Port | Network |
|---|---------|---------|------|---------|
| 1 | `traefik` | Reverse proxy with automatic HTTPS | 80, 443 | bearcave, traefik |
| 2 | `prowlarr` | Indexer manager | 9696 | bearcave |
| 3 | `radarr` | Movie management | 7878 | bearcave |
| 4 | `sonarr` | TV show management | 8989 | bearcave |
| 5 | `nzbdav` | Usenet download client + WebDAV | 3000 | bearcave |
| 6 | `nzbdav_rclone` | FUSE mount sidecar (streams on demand) | — | bearcave |
| 7 | `seerr` | Request manager | 5055 | bearcave |
| 8 | `plex` | Media server | — | host |
| 9 | `metacache` | Metadata cache proxy for Plex | 8765 | bearcave |
| 10 | `control-panel` | Django infrastructure dashboard | 8420 | bearcave |
| 11 | `arr-dashboard` | Next.js media operations dashboard | 41789 | bearcave |
| 12 | `unpackerr` | Auto-extracts downloads | — | bearcave |
| 13 | `cleanuparr` | Cleans orphaned files + failed downloads | 11011 | bearcave |
| 14 | `watchstate` | Tracks what you've watched | 8705 | bearcave |
| 15 | `loki` | Log aggregation | 3100 | bearcave |
| 16 | `promtail` | Log shipping to Loki | — | bearcave |
| 17 | `grafana` | Dashboards + alerting | 3001 | bearcave |
| 18 | `nzbdav-exporter` | NzbDAV config/queue metrics | 9200 | bearcave |
| 19 | `prometheus` | Metrics collection | 9090 | bearcave |
| 20 | `node-exporter` | Host CPU/RAM/disk metrics | 9100 | host |
| 21 | `cadvisor` | Container resource metrics | 8080 | bearcave |
| 22 | `landing-page` | Nginx service portal | 8000 | bearcave |

### Network Topology

- **bearcave** — main bridge network for all Traefik-fronted services
- **traefik** — separate network for Traefik service discovery
- **host** — Plex (GDM/DLNA/remote access) and node-exporter (host metrics) use host networking

Plex is the only service on host network — it cannot be behind Traefik because GDM,
DLNA, and remote-access NAT-PMP/UPnP negotiation are unreliable on bridge networking.

---

## Port Map

```
80    Traefik (HTTP → HTTPS redirect)
443   Traefik (HTTPS)
3000  nzbdav (WebDAV)
3001  Grafana
3100  Loki
5055  Seerr (requests)
7878  Radarr
8000  Landing page
8080  cadvisor
8420  Control Panel (Django)
8705  Watchstate
8765  Metacache
8989  Sonarr
9090  Prometheus
9100  node-exporter
9200  nzbdav-exporter
9696  Prowlarr
11011 Cleanuparr
41789 arr-dashboard (Next.js)
```

---

## Control Panel API (`:8420/api/v2/`)

Django REST framework endpoints. Auth: session cookie or `Authorization: Bearer <key>` for
destructive endpoints (`/api/v2/host/*`). CSRF Origin validation on all POST/PUT/DELETE.

### Host Operations (`/api/v2/host/`)

```
GET  /api/v2/host/status                 — Container status
GET  /api/v2/host/containers             — List all containers
POST /api/v2/host/container/<name>/restart — Restart container
POST /api/v2/host/container/<name>/start   — Start container
POST /api/v2/host/container/<name>/stop    — Stop container
GET  /api/v2/host/container/<name>/logs/stream — Stream logs (SSE)
POST /api/v2/host/stack/restart-all      — Restart all in correct order
GET  /api/v2/host/settings               — Get settings
PATCH /api/v2/host/settings              — Update settings
GET  /api/v2/host/resource-check         — Host resources
GET  /api/v2/host/disk-health            — Disk SMART health
POST /api/v2/host/disk-health/prune      — Prune disk health data
GET  /api/v2/host/host-resources         — CPU/RAM usage
GET  /api/v2/host/log-levels             — Get log levels
POST /api/v2/host/log-levels/reset       — Reset log levels
GET  /api/v2/host/oom-check              — Check OOM kills
GET  /api/v2/host/disk-usage             — Disk usage
GET  /api/v2/host/mount-health           — FUSE mount health
GET  /api/v2/host/perms-check            — File permissions
GET  /api/v2/host/image-check            — Docker image versions
GET  /api/v2/host/version                — Stack version
GET  /api/v2/host/docs/readme            — README content
POST /api/v2/host/notify/test            — Test notifications
GET  /api/v2/host/top                    — Top containers
POST /api/v2/host/reboot                 — Reboot host (requires bearer auth)
POST /api/v2/host/pacman-sync            — Sync pacman databases
POST /api/v2/host/pacman-upgrade         — Upgrade packages
```

### NzbDAV (`/api/v2/nzbdav/`)

```
GET  /api/v2/nzbdav/queue               — Download queue
GET  /api/v2/nzbdav/history             — Download history
GET  /api/v2/nzbdav/dedup-config-check  — Dedup config check
GET  /api/v2/nzbdav/stats               — Download statistics
POST /api/v2/nzbdav/delete-failures     — Delete failed downloads
```

### Cleanuparr (`/api/v2/cleanuparr/`)

```
GET  /api/v2/cleanuparr/instances       — List instances
GET  /api/v2/cleanuparr/strikes         — Show strikes
```

### Watchstate (`/api/v2/watchstate/`)

```
GET  /api/v2/watchstate/status          — Watch state status
POST /api/v2/watchstate/import          — Import watch state
GET  /api/v2/watchstate/history         — Watch history
```

### Queue (`/api/v2/queue/`)

```
GET  /api/v2/queue/status               — Aggregate queue status (Arr + NzbDAV)
```

### Catalog (`/api/v2/catalog/`)

```
GET  /api/v2/catalog/                   — Software catalog
GET  /api/v2/catalog/<id>/status        — Catalog item status
POST /api/v2/catalog/<id>/install       — Install catalog item
POST /api/v2/catalog/<id>/remove        — Remove catalog item
```

### UI Routes (HTMX)

```
/                       — Dashboard overview (infrastructure only)
/host/                  — Container management
/logs/                  — Log viewer with SSE streaming
/settings/              — Settings page
/reference/             — Reference links
/activity/              — Activity log
```

---

## Metacache

Built from source at `services/metacache/`. C#/.NET 10 ASP.NET Core service that caches
TMDB/TVDB metadata locally so Plex refreshes hit LAN instead of internet.

### Key endpoints

```
GET  /movie                — Movie provider definition (Plex registration)
GET  /tv                   — TV provider definition (Plex registration)
POST /library/metadata/matches — Search/match (Plex sends this)
GET  /library/metadata/{ratingKey} — Full metadata
GET  /library/metadata/{ratingKey}/children — Seasons/episodes
GET  /img/{hash}           — Served artwork (local cache)
POST /warm/movies          — Warm cache from Radarr
POST /warm/shows           — Warm cache from Sonarr
GET  /healthz              — Liveness check
GET  /dashboard            — Interactive dashboard
GET  /metrics/prometheus   — Prometheus scrape endpoint
```

### First-run setup

1. Visit `http://HOST_IP:8765/dashboard`
2. Warm cache: `POST /warm/all`
3. In Plex: Settings → Metadata Agents → Add Provider → `http://HOST_IP:8765/movie` (and `/tv`)
4. Create agent, set as primary for library

---

## Technologies

### Backend
- **Python 3.14** — Control panel, scripts, tests
- **Django 5.2** + **Django REST Framework 3.16** — Control panel backend
- **httpx 0.28** — HTTP client for Arr/NzbDAV APIs
- **argon2-cffi** — Password hashing
- **Docker SDK for Python** — Container management
- **SQLite** — Control panel database

### Frontend
- **htmx** — Dynamic UI without JavaScript frameworks
- **Tailwind CSS** — Utility-first styling
- **SSE (Server-Sent Events)** — Live log streaming
- **Next.js 22** — arr-dashboard (separate container)

### Infrastructure
- **Docker Compose** — Service orchestration
- **Traefik v3** — Reverse proxy with automatic HTTPS (Let's Encrypt)
- **rclone** — FUSE mount for streaming content
- **InfiniDysk** — Usenet download client + WebDAV server (formerly nzbdav)
- **Plex** — Media server with hardware transcoding (VAAPI)
- **Metacache** — C#/.NET 10 metadata cache proxy (TMDB/TVDB)

### Monitoring
- **Prometheus** — Metrics collection + alerting rules
- **Grafana** — Dashboards + visualization
- **Loki** — Log aggregation
- **Promtail** — Log shipping
- **cadvisor** — Container resource metrics
- **node-exporter** — Host metrics
- **nzbdav-exporter** — NzbDAV config/queue metrics

### Security
- **Trivy** — CVE scanning (nightly CI + weekly schedule)
- **Dependabot** — NuGet, Docker, pip, GitHub Actions updates (weekly)
- **CodeQL** — Code scanning for Python and C#
- **ShellCheck** — Shell script linting
- **Ruff** — Python linting

### CI/CD
- **GitHub Actions** — 11 workflows
  - `validate.yml` — compose validation, env coverage, shellcheck, ruff, Django tests
  - `release-please.yml` — automated release management
  - `trivy-scan.yml` — CVE scan all 22 images, IaC config scan, baseline report
  - `dotnet-ci.yml` — .NET build/format/test/coverage/NuGet CVE audit for metacache
  - `docker-publish.yml` — build+push metacache to GHCR, nightly Trivy rescan
  - `codeql.yml` — CodeQL security analysis (Python + C#)
  - `nightly-healthcheck.yml` — daily compose/Dockerfile/script/config validation
  - `pr-labeler.yml` — auto-label PRs by size and file paths
  - `pr-lint.yml` — enforce Conventional Commits in PR titles
  - `stale.yml` — auto-close stale issues and PRs
  - `dependabot.yml` — automated dependency updates

### Languages
- **Python** — Control panel + scripts
- **Bash** — System scripts, CI steps
- **C# / .NET 10** — Metacache metadata cache proxy
- **TypeScript** — arr-dashboard (Next.js)
- **YAML** — Docker Compose, CI/CD workflows

---

## Configuration

### Environment Variables

All secrets live in `.env` (never committed). See `.env.template` for the full list.
Key groups:

| Variable | Purpose |
|----------|---------|
| `RADARR_API_KEY` | Radarr API authentication |
| `SONARR_API_KEY` | Sonarr API authentication |
| `PROWLARR_API_KEY` | Prowlarr API authentication |
| `PLEX_TOKEN` | Plex authentication |
| `TMDB_KEY` | TMDB API key (read access token) |
| `TVDB_KEY` | TVDB API key |
| `NZBDAV_WEBDAV_USER/PASS` | WebDAV authentication |
| `NZBDAV_RCLONE_RC_PASS` | rclone remote control password |
| `WS_API_KEY` | Watchstate API key |
| `METACACHE_API_KEY` | Metacache API key |
| `CONTROL_PANEL_SECRET_KEY` | Django secret key |
| `TRAEFIK_DASHBOARD_AUTH` | Traefik dashboard basic auth |
| `HOST_IP` | Host IP address (used for Traefik routing) |

### Docker Secrets

Sensitive values should be stored in `secrets/` directory (gitignored).
Run `./scripts/setup.sh` to generate secrets.

### Platform Constraints

- **Linux only** — `host.docker.internal` used for Prometheus→node-exporter scraping
- **Port 8080** — cAdvisor uses this; ensure no conflicts
- **FUSE mounts** — nzbdav_rclone requires `/dev/fuse` and `SYS_ADMIN` capability

---

## Historical Issues and Landmines

### Critical Landmines (affect operations today)

1. **FUSE mount fragility** — Mount-owner restart breaks all dependents. Never `sudo umount` a FUSE mountpoint. Restart the owner, then all dependents in order.

2. **Plex `stop_grace_period: 90s` required** — Without it, Docker's 10s default SIGKILL fires mid-shutdown, producing a genuine unkillable D-state hang.

3. **NzbDAV queue is not persistent** — Recreate wipes queued NZBs and silently blocklists affected items. Confirm pending is 0 before touching.

4. **Control Panel reads .env at create time only** — `restart` doesn't pick up .env changes. Use `--force-recreate`.

5. **Traefik + Plex separation** — Plex runs on host network and cannot be behind Traefik. Access directly at `http://HOST_IP:32400`.

6. **rclone.conf requires `rclone obscure`** — Passwords in rclone.conf must be rclone-obfuscated, not plaintext.

7. **App removal checklists must be exhaustive** — Every removal touches: compose, config, env vars, Prowlarr sync, Cleanuparr, Control Panel, traefik labels.

---

## How to Work in This Repo

### Before Making Changes

1. Read `CLAUDE.md` for work style rules
2. Check `docker compose ps` for current state
3. Read `docs/` for service documentation

### After Making Changes

1. Run validation: `docker compose config --quiet`
2. Run bash syntax checks: `bash -n scripts/*.sh tests/*/*.sh`
3. Run health checks: `./tests/health/run-all.sh`
4. Run integration tests: `./tests/integration/test_pipeline.sh`

### Safety Rules

- Never commit `.env` or secrets
- Never run destructive operations without confirmation
- Always restart dependents after mount-owner changes
- Always confirm NzbDAV queue is empty before container operations
- Use `--force-recreate` when .env changes need to take effect
- Plex config directory contains the full library metadata — back up before changes

---

## Archive

Legacy files from the source repos are preserved in `archive/`:
- `archive/media-stack/` — 133+ fish functions, scripts, systemd units, CLAUDE.md, STACK.md
- `archive/metacacharr/` — DESIGN.md, tests, monitoring configs

These are reference material only — not part of the active stack.
