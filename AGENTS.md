# AGENTS.md

Complete reference for AI coding agents working in this repo. Read `CLAUDE.md` first for
work style and non-negotiable rules — this file covers the system itself.

---

## What This Repo Is

A unified media-acquisition-and-serving stack. 30 configured Compose services, a Next.js
arr-dashboard, Prometheus/Grafana monitoring, Traefik reverse proxy,
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
          (Infrastructure)       (Media Operations)
                    │                   │
              Prometheus :9090    Grafana :3001
```

### Service Categories

| Category | Services |
|----------|----------|
| **Reverse proxy** | Traefik (ports 80/443) |
| **Indexing** | Prowlarr |
| **\*arr apps** | Radarr (movies), Sonarr (TV), Lidarr (music), Readarr (books) |
| **Usenet** | InfiniDysk/nzbdav + nzbdav_rclone sidecar |
| **Requests** | Seerr |
| **Media server** | Plex (host network, VAAPI transcoding), Audiobookshelf, Komga |
| **Metadata** | Metacache (built from source, TMDB/TVDB cache) |
| **Queue mgmt** | Unpackerr |
| **Watch state** | WatchState |
| **Logging** | Loki, Promtail, Grafana |
| **Metrics** | Prometheus, Node Exporter, cAdvisor, nzbdav-exporter |
| **ARR dashboard** | arr-dashboard |
| **Landing page** | Nginx |
| **Network/security** | AdGuard Home, CrowdSec |
| **Utilities** | Vaultwarden, n8n |

### Dashboard Surface

| Panel | Port | Technology | Responsibilities |
|-------|------|------------|-----------------|
| **arr-dashboard** | 41789 | Next.js (Node 22) | Multi-instance queue/calendar/history, TRaSH Guides, library cleanup, auto-hunting, Plex analytics, notifications, statistics |

Talks independently to Radarr/Sonarr/Prowlarr APIs.

- **Content flow:** Prowlarr indexes → Radarr/Sonarr queue → nzbdav downloads → rclone FUSE mount → Plex serves
- **Metadata:** Metacache (:8765) caches TMDB/TVDB lookups locally so Plex refreshes hit cache
- **Observability:** Prometheus scrapes node-exporter, cadvisor, nzbdav-exporter, metacache. Loki ingests Docker logs via Promtail. Grafana queries both.
- **Reverse proxy:** Traefik routes all services except Plex (which uses host network) via Host-based routing with automatic HTTPS.
- **Landing page is registry-driven:** `services/landing-page/service-registry.json` is the single source of truth for all 30 configured services (name, port, category, dependencies, health endpoint, dashboard URL). An inline copy in `index.html` powers the card grid and pipeline flow strip. Adding a service requires updating both files.

---

## Services (30 configured services)

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
| 10 | `arr-dashboard` | Next.js media operations dashboard | 41789 | bearcave |
| 11 | `unpackerr` | Auto-extracts downloads | — | bearcave |
| 13 | `bazarr` | Subtitle management | 6767 | bearcave |
| 14 | `lidarr` | Music acquisition | 8686 | bearcave |
| 15 | `readarr` | Ebook acquisition | 8787 | bearcave |
| 16 | `audiobookshelf` | Audiobook/podcast server | 13378 | bearcave |
| 17 | `komga` | Comics/manga server | 25600 | bearcave |
| 18 | `adguard` | LAN DNS ad/tracker blocker | 3003 | bearcave |
| 19 | `crowdsec` | Intrusion detection | 18080 | bearcave |
| 20 | `vaultwarden` | Self-hosted password manager | 8222 | bearcave |
| 21 | `n8n` | Workflow automation | 5678 | bearcave |
| 22 | `watchstate` | Tracks what you've watched | 8705 | bearcave |
| 23 | `loki` | Log aggregation | 3100 | bearcave |
| 24 | `promtail` | Log shipping to Loki | — | bearcave |
| 25 | `grafana` | Dashboards + alerting | 3001 | bearcave |
| 26 | `nzbdav-exporter` | NzbDAV config/queue metrics | 9200 | bearcave |
| 27 | `prometheus` | Metrics collection | 9090 | bearcave |
| 28 | `node-exporter` | Host CPU/RAM/disk metrics | 9100 | host |
| 29 | `cadvisor` | Container resource metrics | 8080 | bearcave |
| 30 | `landing-page` | Nginx service portal | 8000 | bearcave |
| 31 | `alertmanager` | Prometheus alert routing + Discord notifications | 9093 | bearcave |


### Network Topology

- **bearcave** — main bridge network for all Traefik-fronted services
- **traefik** — separate network for Traefik service discovery
- **host** — Plex (GDM/DLNA/remote access) and node-exporter (host metrics) use host networking

Plex is the only service on host network — it cannot be behind Traefik because GDM,
DLNA, and remote-access NAT-PMP/UPnP negotiation are unreliable on bridge networking.

### Expansion Services (deployed — see `stack-expansion-spec.md`)

The 10-service expansion in `stack-expansion-spec.md` is deployed: nine
services are live in `docker-compose.yml` (Lidarr, Readarr, Bazarr,
Audiobookshelf, Komga, AdGuard Home, CrowdSec, Vaultwarden, n8n). The tenth,
Uptime Kuma, was removed from scope by decision. Docs pages exist in
`docs/services/`:

| Service | Purpose | Port | Docs |
|---------|---------|------|------|
| `lidarr` | Music acquisition | 8686 | [docs/services/lidarr.md](docs/services/lidarr.md) |
| `readarr` | Ebook acquisition | 8787 | [docs/services/readarr.md](docs/services/readarr.md) |
| `bazarr` | Subtitles for movies/shows | 6767 | [docs/services/bazarr.md](docs/services/bazarr.md) |
| `audiobookshelf` | Audiobook/podcast server | 13378 | [docs/services/audiobookshelf.md](docs/services/audiobookshelf.md) |
| `komga` | Comics/manga server | 25600 | [docs/services/komga.md](docs/services/komga.md) |
| `adguard` | LAN DNS ad/tracker blocker | 53, 3003 | [docs/services/adguard.md](docs/services/adguard.md) |
| `crowdsec` | Intrusion detection (Traefik plugin bouncer) | 18080 | [docs/services/crowdsec.md](docs/services/crowdsec.md) |
| `vaultwarden` | Self-hosted password manager | 8222 | [docs/services/vaultwarden.md](docs/services/vaultwarden.md) |
| `n8n` | Workflow automation (Discord notifications first) | 5678 | [docs/services/n8n.md](docs/services/n8n.md) |

Key cross-cutting items from the spec: the nzbdav category rollout (§15,
queue-gated) preceded Phases 1 acquisitions; CVE posture gates some images
(§14 — lidarr `:nightly`, komga `1.x`); the Crowdsec bouncer is a Traefik
middleware plugin, not a sidecar (§4.8).

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
8705  Watchstate
8765  Metacache
8989  Sonarr
9090  Prometheus
9100  node-exporter
9200  nzbdav-exporter
9696  Prowlarr
6767  Bazarr
8686  Lidarr
8787  Readarr
13378 Audiobookshelf
25600 Komga
3003  AdGuard Home
18080 CrowdSec
8222  Vaultwarden
5678  n8n
41789 arr-dashboard (Next.js)
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
- **Python 3.14** — Scripts, tests, nzbdav-exporter
- **SQLite** — Local app state (arr-dashboard)

### Frontend
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
- **Dependabot** — NuGet, Docker, pip updates (weekly); GitHub Actions are SHA-pinned so action upgrades are manual (see docs/ci-cd.md)
- **CodeQL** — Code scanning for Python and C#
- **ShellCheck** — Shell script linting
- **Ruff** — Python linting

### CI/CD
- **GitHub Actions** — 14 workflows; full policy in [docs/ci-cd.md](docs/ci-cd.md)
  - **All third-party actions are SHA-pinned** (immutable supply chain); the `# tag` comment records the version. Upgrade path: `gh api repos/{owner}/{repo}/commits/{tag} --jq .sha`, then update SHA + comment. Dependabot cannot auto-bump SHA pins.
  - **release-please only opens PRs for `feat:`/`fix:` commits.** `ci:`, `docs:`, `chore:` do not trigger a release. If you need to cut a release, ensure at least one commit uses a release-worthy type.
  - **Brand-new repo race condition:** workflows added in the initial push of a new repo may not trigger on push/PR events. Manual dispatch works. Re-adding or renaming the workflow file fixes it.
  - **actionlint gates every workflow change** in `validate.yml` — syntax, expressions, action refs, and shellcheck on `run:` blocks. Replicate locally: download the pinned actionlint release binary and run `actionlint .github/workflows/*.yml`.
  - `validate.yml` — compose validation, env coverage, shellcheck, ruff, actionlint, exporter unit tests
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
- **Python** — Scripts, tests, nzbdav-exporter
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
| `TRAEFIK_DASHBOARD_AUTH` | Traefik dashboard basic auth |
| `HOST_IP` | Host IP address (used for Traefik routing) |
| `RELEASE_PLEASE_TOKEN` | PAT for release-please to create release PRs and push tags (required for automated releases) |

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

1. **Bind-mount file staleness** — `sed -i`/`vim` on a bind-mounted file changes the inode; the container keeps serving the old file until restarted. Always `docker compose restart <container>` after editing a file served by a bind mount. The landing page has been bitten twice (badge fetch URL, then link repoint).
2. **Self-signed cert warning** — Traefik's default cert is a self-signed `TRAEFIK DEFAULT CERT` that browsers reject. The stack uses mkcert to issue LAN-trusted certs (see `docs/landmines.md`). Devices must install `rootCA.pem` from the landing page. The `nip.io` domain is for routing only — it cannot get a real ACME cert.
3. **FUSE mount fragility** — Mount-owner restart breaks all dependents. Never `sudo umount` a FUSE mountpoint. Restart the owner, then all dependents in order.

4. **Plex `stop_grace_period: 90s` required** — Without it, Docker's 10s default SIGKILL fires mid-shutdown, producing a genuine unkillable D-state hang.

5. **NzbDAV queue is not persistent** — Recreate wipes queued NZBs and silently blocklists affected items. Confirm pending is 0 before touching.

6. **Traefik + Plex separation** — Plex runs on host network and cannot be behind Traefik. Access directly at `http://HOST_IP:32400`.

7. **rclone.conf requires `rclone obscure`** — Passwords in rclone.conf must be rclone-obfuscated, not plaintext.

8. **App removal checklists must be exhaustive** — Every removal touches: compose, config, env vars, Prowlarr sync, traefik labels.

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
5. **Restart containers after editing bind-mounted files** — `sed -i` or `vim` on a bind-mounted file changes the inode; the container keeps serving the old content until restarted. This is invisible (no error) and has bitten twice on the landing page.

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

**Watch out:** `services/metacache/monitoring/` contains a stale duplicate `docker-compose.yml` and `prometheus.yml` from the metacacharr source repo. These are not part of the active stack and could confuse operators or accidentally override the main stack's monitoring.
