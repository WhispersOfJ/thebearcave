# The Bear Cave

**A unified, Usenet-only media stack — 29 configured services, one `docker compose up -d`.**

Combines the media-stack and metacacharr repos into a single deployment: Prowlarr
indexing → *arr acquisition → NzbDAV/InfiniDysk Usenet downloads → rclone FUSE streaming →
Plex serving, with a self-hosted metadata cache, full observability, and Discord alerting.
Every download is streamed on demand — no media sits on local disk.

> **Operational reference:** [AGENTS.md](AGENTS.md) is the authoritative, always-current
> reference for how the stack works. This README is the human-facing overview; when they
> disagree, AGENTS.md wins.

## At a glance

| Metric | Value |
|--------|-------|
| Configured services | **29** (all running, `docker compose ps` shows every one up) |
| Acquisition apps | 4 — Radarr, Sonarr, Lidarr, Readarr |
| Indexers (via Prowlarr) | 3 — DrunkenSlug, NZBgeek, NzbPlanet |
| Download client | NzbDAV (InfiniDysk) — SABnzbd-compatible |
| Media libraries | Movies, Shows (+ Anime Movies / Anime Shows) |
| Monitoring | Prometheus + Grafana + Loki + Alertmanager → Discord |
| Security | CrowdSec, Trivy CVE baseline, CodeQL, OpenSSF Scorecard, Secret Guard |

## Architecture

```
                    ┌──────────────────────────────┐
                    │  Traefik :80/:443 (HTTPS)     │   fronts every service
                    │  + CrowdSec bouncer middleware│   except Plex
                    └──────────────┬───────────────┘
                                   │ indexes
                                   ▼
        Prowlarr :9696 ──▶ Radarr :7878 / Sonarr :8989 / Lidarr :8686 / Readarr :8787
                                   │  (SABnzbd-compatible download client)
                                   ▼
                           NzbDAV (InfiniDysk) :3000        • queue + download
                                   │  rclone FUSE mount     • WebDAV source of truth
                                   ▼
                        nzbdav_rclone  /mnt/remote/nzbdav
                                   │  :rslave bind mounts (stream on demand)
                             ┌─────┼──────┬──────┐
                             ▼     ▼      ▼      ▼
                          Plex  Bazarr  ABS   Komga    (media consumed, zero local files)

Plex :32400 (host network) ─┬─ Metacache :8765 (metadata agent)
                              WatchState :8705 (watch sync)
                              Radarr/Sonarr (import-complete → library scan)
```

Interactive mermaid versions of the topology, data flow, FUSE lifecycle, and dependency
chains live in [docs/architecture.md](docs/architecture.md).

## Services (29)

| Service | Port | Purpose | Network |
|---------|------|---------|---------|
| **Traefik** | 80, 443 | Reverse proxy, automatic HTTPS, CrowdSec bouncer | traefik |
| **Prowlarr** | 9696 | Indexer management (3 indexers) | bearcave |
| **Radarr** | 7878 | Movie acquisition | bearcave |
| **Sonarr** | 8989 | TV acquisition | bearcave |
| **Lidarr** | 8686 | Music acquisition | bearcave |
| **Readarr** | 8787 | Book acquisition | bearcave |
| **NzbDAV** | 3000 | Usenet download client + WebDAV (InfiniDysk) | bearcave |
| **nzbdav_rclone** | — | FUSE mount, streams on demand | bearcave |
| **Unpackerr** | — | Auto-extracts downloads for all four *arr | bearcave |
| **Bazarr** | 6767 | Subtitles for Radarr/Sonarr/Plex | bearcave |
| **Seerr** | 5055 | Requests + discovery (Radarr/Sonarr/Plex) | bearcave |
| **Plex** | 32400 | Media server (host network) | host |
| **Metacache** | 8765 | Plex metadata cache / agent (TMDB/TVDB) | bearcave |
| **Audiobookshelf** | 13378 | Audiobook & podcast server | bearcave |
| **Komga** | 25600 | Comics & manga server | bearcave |
| **WatchState** | 8705 | Watch-state sync (Plex → history) | bearcave |
| **arr-dashboard** | 41789 | Multi-*arr queue/calendar/analytics UI | bearcave |
| **Grafana** | 3001 | Dashboards & alerting UI | bearcave |
| **Prometheus** | 9090 | Metrics collection + MCP-baseline alert | bearcave |
| **Alertmanager** | 9093 | Alert routing → Discord | bearcave |
| **Loki** | 3100 | Log aggregation | bearcave |
| **Promtail** | — | Log shipping → Loki | bearcave |
| **node-exporter** | 9100 | Host metrics (host network) | host |
| **cadvisor** | 8080 | Container metrics | bearcave |
| **nzbdav-exporter** | 9200 | NzbDAV config/queue metrics | bearcave |
| **Landing page** | 8000 | Nginx service portal (registry-driven) | bearcave |
| **AdGuard Home** | 53, 3003 | LAN DNS filtering | bearcave |
| **CrowdSec** | 18080 | Intrusion detection (Traefik bouncer) | bearcave |
| **Vaultwarden** | 8222 | Private password manager | bearcave |

## How the apps connect

The stack is wired as an acquisition pipeline with the *arr apps at the center:

- **Indexing** — Prowlarr syncs its 3 indexers to **Radarr, Sonarr, Lidarr, Readarr**
  (Prowlarr *applications*). Each *arr sees the same indexers.
- **Downloading** — all four *arr apps point at **NzbDAV** as a SABnzbd-compatible
  client (`nzbdav:3000`), with categories `movies` / `tv` / `music` / `books`. Unpackerr
  watches all four queues for extraction.
- **Streaming** — NzbDAV's WebDAV tree is FUSE-mounted by **nzbdav_rclone** at
  `/mnt/remote/nzbdav`; **Plex**, **Bazarr**, **Audiobookshelf**, and **Komga** read that
  mount directly (`:rslave`), so playback streams on demand with no local copies.
- **Serving metadata** — **Metacache** is Plex's metadata agent and **WatchState** backs
  up watch history from Plex.
- **Subtitles & requests** — **Bazarr** pulls subtitles from Radarr/Sonarr (+ Plex);
  **Seerr** handles requests into Radarr/Sonarr and Plex watchlists.
- **Plex feedback** — Radarr/Sonarr notify **Plex** on import to trigger a library scan.
- **Observability** — **Prometheus** scrapes node-exporter, cadvisor, nzbdav-exporter,
  and metacache; **Promtail** ships logs to **Loki**; Grafana queries both;
  **Alertmanager** routes alerts to **Discord** (e.g. the daily MCP-baseline check).

## Security

- **CrowdSec** as a Traefik middleware bouncer — intrusion detection at the edge.
- **Trivy** CVE scanning nightly + weekly, gated on CRITICAL regressions vs a committed
  baseline (`.github/trivy-baseline.json`).
- **CodeQL** (Python + C#) on every push/PR; **NuGet** CVE audit via `dotnet-ci`.
- **OpenSSF Scorecard** supply-chain analysis on main pushes.
- **Secret Manifest Guard** (`secret-guard.yml`) fails CI when a workflow uses an
  undeclared secret.
- **Every third-party GitHub Action is SHA-pinned** (mutable tags rejected); workflows are
  **actionlint-gated**.
- Secrets live in gitignored `.env` / `secrets/`; the stack intentionally exposes only
  authenticated service surfaces. See [docs/security.md](docs/security.md) for the full
  model and tradeoffs.

## Testing

```bash
./scripts/preflight.sh          # one-command pre-push gate: ruff, py_compile, actionlint,
                                # compose config, merged-mount + mount-drift checks, MCP baseline,
                                # Grafana dashboard JSON — what CI's validate runs
./tests/health/run-all.sh       # health-check every configured service
./tests/integration/test_pipeline.sh    # FUSE mount → Plex → *arr → NzbDAV → Metacache
./tests/integration/test_backup_restore.sh
./tests/integration/test_landing_page.sh
./tests/fish/test_fish_functions.sh     # fish shell tools (parse + live smoke)
```

CI (`validate.yml`) runs the preflight suite plus shellcheck and exporter unit tests on
every push; the nightly-healthcheck workflow validates the live stack daily.

## Statistics

- **29/29 services up** — the full `docker compose ps` set is healthy.
- **4 acquisition apps** (Radarr/Sonarr/Lidarr/Readarr) sharing **3 indexers** through
  Prowlarr, all funneling downloads into a single NzbDAV client.
- **~1,000 completed downloads** tracked in NzbDAV history, with movies and TV delivered
  into FUSE-streamed symlink libraries (no local media storage).
- **Observability spans 5 Prometheus targets** (node, cadvisor, NzbDAV, metacache, Prometheus
  itself) plus Loki log aggregation and Discord alerting.

## Quick start

```bash
# 1. Clone and configure
git clone https://github.com/WhispersOfJ/thebearcave.git
cd thebearcave
cp .env.template .env        # edit with real values (see .env.template)
./scripts/setup.sh           # generate Docker secrets (recommended)

# 2. Start the stack
docker compose up -d

# 3. Verify
docker compose ps            # all 29 up
./scripts/preflight.sh       # local CI-equivalent gate

# Zero-to-streaming walkthrough: docs/quick-start.md
```

## Configuration

- **Environment variables** — see `.env.template` for the full inventory (API keys,
  NzbDAV/Usenet credentials, Plex token, TMDB/TVDB keys, Discord webhook…).
- **Secrets** — Docker secrets in `secrets/`, initialized by `scripts/setup.sh`.
- **Traefik** — auto-HTTPS for every service except Plex. Reach services at
  `https://<service>.{HOST_IP}.nip.io` (LAN-trusted certs via mkcert).
- **Plex** — host network for GDM/DLNA/remote access; direct at `http://{HOST_IP}:32400`.

## Documentation

| Doc | What it covers |
|-----|----------------|
| [AGENTS.md](AGENTS.md) | **Full operational reference** (services, ports, landmines, workflows) |
| [Architecture](docs/architecture.md) | Mermaid diagrams: topology, data flow, FUSE lifecycle, dependencies |
| [Quick Start](docs/quick-start.md) | Zero-to-streaming + day-1 checklist |
| [Services](docs/services/) | Per-service docs, incl. [lifecycle](docs/services/lifecycle.md) (retired + re-adoption) |
| [Landmines](docs/landmines.md) | Operational gotchas that bite |
| [Operations](docs/operations/) | Backup/restore, troubleshooting |
| [Security](docs/security.md) | Secrets model, exposure, tradeoffs, incident response |
| [CI/CD](docs/ci-cd.md) | Workflows, pinned-actions policy, actionlint gate, releases |
| [Testing](docs/testing.md) | Health checks, integration pipeline, live tests |
| [MCP](docs/mcp.md) | Freebuff Desktop MCP setup |
| [Migration](docs/migration/) | from-media-stack / from-metacacharr guides |

## Platform constraints

- **Linux only** — uses `host.docker.internal:9100` for host metrics; fails on macOS/Windows
  Docker Desktop.
- **Port 8080** — cadvisor binds the host port; keep it free.
- **FUSE** — `nzbdav_rclone` requires `/dev/fuse` and `SYS_ADMIN`.
- **Plex host network** — cannot sit behind Traefik (GDM/DLNA/remote access).

## Contributing

See [CLAUDE.md](CLAUDE.md) for development guidelines, and run
`scripts/preflight.sh` before opening a PR.

## License

MIT — see [LICENSE](LICENSE). Third-party images/services keep their own licenses.