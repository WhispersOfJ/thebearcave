# The Bear Cave

**A unified media infrastructure stack — 21 containers, one `docker compose up -d`.**

Combines all services from media-stack and metacacharr into a single, cohesive deployment. Usenet-only, FUSE-streamed, Plex-served, with a custom metadata cache for fast local updates.

## Architecture

```
┌──────────┐   indexes   ┌──────────────────────────────┐   serves   ┌──────┐
│ Prowlarr │────────────▶│       Radarr  +  Sonarr      │───────────▶│ Plex │
│  :9696   │             │    :7878/:7879  :8989/:8990  │            │ host │
└──────────┘             └──────────┬───────────────────┘            └──┬───┘
                                    │ grab NZBs                        │
                                    ▼                                  │
                         ┌────────────────────┐                        │
                         │      nzbdav        │  WebDAV + SAB-API     │
                         │  InfiniDysk :3000  │◄──────────────────────┘
                         └────────┬───────────┘   symlink imports
                                  │
                                  ▼
                         ┌────────────────────┐
                         │   nzbdav_rclone    │  rclone FUSE mount
                         │  /mnt/remote/nzbdav│  streamed on demand
                         └────────┬───────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              ./media/movies  ./media/shows  ./media/anime-*
              (100% symlinks, zero real files on local disk)

┌────────────────────┐         ┌────────────────────┐
│   Metacache        │         │     Traefik         │
│   Custom Metadata  │         │   Reverse Proxy     │
│   Provider :8765   │         │   :80/:443          │
└────────────────────┘         └────────────────────┘
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| **Traefik** | 80, 443 | Reverse proxy with automatic HTTPS |
| **Prowlarr** | 9696 | Indexer management |
| **Radarr** | 7878 | Movie management |
| **Sonarr** | 8989 | TV show management |
| **InfiniDysk** | 3000 | Usenet streaming/download |
| **Seerr** | 5055 | Request management |
| **Plex** | 32400 | Media server (host network) |
| **Metacache** | 8765 | Custom metadata provider |
| **WatchState** | 8705 | Watch state sync |
| **Grafana** | 3001 | Dashboards & monitoring |
| **Prometheus** | 9090 | Metrics storage |
| **Loki** | 3100 | Log aggregation |

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/thebearcave.git
cd thebearcave

# 2. Copy and configure environment
cp .env.template .env
# Edit .env with your actual values

# 3. Set up Docker secrets (optional, recommended)
./scripts/setup.sh

# 4. Start the stack
docker compose up -d

# 5. Verify all services are healthy
docker compose ps
./tests/health/run-all.sh
```

## Configuration

### Environment Variables

See `.env.template` for all required and optional configuration variables.

### Secrets Management

The Bear Cave uses Docker secrets for sensitive values. See `secrets/` directory and `scripts/setup.sh` for initialization.

### Traefik

All services except Plex are fronted by Traefik with automatic HTTPS. Access services via:
- `https://radarr.{HOST_IP}.nip.io`
- `https://sonarr.{HOST_IP}.nip.io`
- `https://panel.{HOST_IP}.nip.io`
- etc.

### Plex

Plex runs on host network for GDM/DLNA/remote access. Access directly at `http://{HOST_IP}:32400`.

## Documentation

| Doc | What it covers |
|-----|----------------|
| [Architecture](docs/architecture.md) | Mermaid diagrams: topology, data flow, FUSE lifecycle, dependencies |
| [Quick Start](docs/quick-start.md) | Zero-to-streaming in ~30 min + day-1 checklist |
| [Services](docs/services/) | Per-service docs for all 22 containers |
| [Landmines](docs/landmines.md) | Operational gotchas that bite — read before touching the stack |
| [Operations](docs/operations/backup-restore.md) | Backup, restore, DR checklist |
| [Operations](docs/operations/troubleshooting.md) | Symptom-driven playbooks |
| [Security](docs/security.md) | Secrets model, exposure, tradeoffs, incident response |
| [CI/CD](docs/ci-cd.md) | Workflows, pinned-actions policy, actionlint gate, release automation |
| [Testing](docs/testing.md) | Health checks, integration pipeline, live tests |
| [Migration](docs/migration/) | from-media-stack / from-metacacharr guides |
| [AGENTS.md](AGENTS.md) | Full system reference for AI agents |

## Testing

```bash
# Run all health checks (22 services)
./tests/health/run-all.sh

# Integration pipeline (FUSE mount, Plex, *arr, InfiniDysk, Metacache)
./tests/integration/test_pipeline.sh

# Live tests (streaming, playback) — see docs/testing.md
```

## Platform Constraints

- **Linux only:** The Bear Cave uses `host.docker.internal` for Prometheus to scrape node-exporter on port 9100. This works on Linux via `extra_hosts: host.docker.internal:host-gateway` but **fails on Docker Desktop for Mac/Windows** where the DNS resolution differs. Do not run this stack on non-Linux hosts.
- **Port 8080:** cAdvisor binds to host port 8080. Ensure no other service on the host uses this port.
- **FUSE mounts:** The nzbdav_rclone sidecar requires `/dev/fuse` and `SYS_ADMIN` capability. Ensure your Docker runtime supports FUSE passthrough.

## Roadmap


## Contributing

See [CLAUDE.md](CLAUDE.md) for development guidelines.

## License

[Your License Here]
