# The Bear Cave

**A lean, Usenet-only media stack — 8 always-on containers, one `docker compose up -d`.**

Prowlarr indexing → Radarr/Sonarr acquisition → NzbDAV (InfiniDysk) Usenet downloads →
rclone FUSE streaming → Plex serving, with Seerr handling requests. Every download is
streamed on demand — no media sits on local disk.

> **Operational reference:** [AGENTS.md](AGENTS.md) is the authoritative, always-current
> reference for how the stack works. This README is the human-facing overview; when they
> disagree, AGENTS.md wins.

> **2026-08-30 slim-down:** the stack was deliberately pared down from 29 services to 8
> (observability, Traefik front, long-tail acquisition, and security sidecars retired).
> Retired services and re-adoption criteria live in
> [docs/services/lifecycle.md](docs/services/lifecycle.md).

## At a glance

| Metric | Value |
|--------|-------|
| Always-on containers | **8** (`docker compose ps`) |
| Acquisition apps | 2 — Radarr (movies), Sonarr (TV) |
| Download client | NzbDAV (InfiniDysk) — SABnzbd-compatible |
| Media libraries | Movies, Shows |
| Requests | Seerr → Radarr/Sonarr/Plex watchlists |
| Manual maintenance | ImageMaid PhotoTranscoder cache cleanup (profile-gated) |
| Memory caps | ≈11.1 GiB total (was ~19 GiB before the slim-down); CPU quotas tuned for scans/downloads |

## Architecture

```
  Seerr :5055 ──requests──▶ Radarr :7878 / Sonarr :8989
                                 │  (SABnzbd-compatible download client)
                                 ▼
                     NzbDAV (InfiniDysk) :3000      • queue + download
                                 │  rclone FUSE mount   • WebDAV source of truth
                                 ▼
                      nzbdav_rclone  /mnt/remote/nzbdav
                                 │  :rslave bind mounts (stream on demand)
                                 ▼
                               Plex :32400  (host network, streams on demand)

  Unpackerr ── watches *arr queues, auto-extracts
```

No reverse proxy: all services are reached directly on their host ports over LAN.

## Services (8)

| Service | Port | Purpose | Network |
|---------|------|---------|---------|
| **Prowlarr** | 9696 | Indexer management | bearcave |
| **Radarr** | 7878 | Movie acquisition | bearcave |
| **Sonarr** | 8989 | TV acquisition | bearcave |
| **NzbDAV** | 3000 | Usenet download client + WebDAV (InfiniDysk) | bearcave |
| **nzbdav_rclone** | — | FUSE mount, streams on demand | bearcave |
| **Unpackerr** | — | Auto-extracts downloads for Radarr/Sonarr | bearcave |
| **Seerr** | 5055 | Requests + discovery (Radarr/Sonarr/Plex) | bearcave |
| **Plex** | 32400 | Media server (host network) | host |

## How the apps connect

- **Indexing** — Prowlarr syncs its indexers to **Radarr** and **Sonarr** (Prowlarr
  *applications*). Both *arr apps see the same indexers.
- **Downloading** — both *arr apps point at **NzbDAV** as a SABnzbd-compatible client
  (`nzbdav:3000`), with categories `movies` / `tv`. **Unpackerr** watches both queues.
- **Streaming** — NzbDAV's WebDAV tree is FUSE-mounted by **nzbdav_rclone** at
  `/mnt/remote/nzbdav`; **Plex** reads that mount directly (`:rslave`), so playback
  streams on demand with no local copies.
- **Requests** — **Seerr** handles requests into Radarr/Sonarr and Plex watchlists.
- **Plex feedback** — Radarr/Sonarr notify **Plex** on import to trigger a library scan.
- **ImageMaid** — optional maintenance profile removes generated PhotoTranscoder cache
  files only; run `stack-plex-image-clean` while Plex is idle.

## Memory caps

Rebalanced during the slim-down (total ≈11.1 GiB, down from ~19 GiB); quotas are sized to avoid observed scan/download throttling:

| Service | Cap |
|---------|-----|
| plex | 2g |
| nzbdav | 2.5g |
| nzbdav_rclone | 3g |
| radarr | 1.5g (1.5 CPU) |
| sonarr | 1g (1.5 CPU) |
| prowlarr | 512m |
| seerr | 512m |
| unpackerr | 64m |

## Testing

```bash
docker compose config --quiet    # compose validation
./tests/health/run-all.sh        # health-check every configured service
./tests/integration/test_pipeline.sh   # FUSE mount → Plex → *arr → NzbDAV
./tests/fish/test_fish_functions.sh    # fish shell tools (parse + live smoke)
./tests/bash/test_bash_functions.sh   # bash port tools (parse + drift + guard)
```

## Git hooks

Install the repo's pre-push gate — it runs `./scripts/preflight.sh` (ruff, compose
config, the secret-drift guard, DB-integrity checks) before every `git push`:

```bash
./scripts/install-git-hooks.sh
```

Escape hatch: `git push --no-verify` (only after understanding what failed).
Uninstall: `git config --unset core.hooksPath`.

## Quick start

```bash
# 1. Clone and configure
git clone https://github.com/WhispersOfJ/thebearcave.git
cd thebearcave
cp .env.template .env        # edit with real values (see .env.template)

# 2. Start the stack
docker compose up -d

# 3. Verify
docker compose ps            # all 8 up
```

## Configuration

- **Environment variables** — see `.env.template` for the full inventory (API keys,
  NzbDAV/Usenet credentials, Plex token).
- **Plex** — host network for GDM/DLNA/remote access; direct at `http://{HOST_IP}:32400`.

## Documentation

| Doc | What it covers |
|-----|----------------|
| [AGENTS.md](AGENTS.md) | **Full operational reference** (services, ports, landmines, workflows) |
| [Services](docs/services/) | Per-service docs, incl. [ImageMaid maintenance](docs/services/imagemaid.md) and [lifecycle](docs/services/lifecycle.md) (retired + re-adoption) |
| [Landmines](docs/landmines.md) | Operational gotchas that bite |
| [Operations](docs/operations/) | Backup/restore, troubleshooting |

## Platform constraints

- **Linux only** — FUSE mount semantics and bind-mount layout assume Linux Docker.
- **FUSE** — `nzbdav_rclone` requires `/dev/fuse` and `SYS_ADMIN`.
- **Plex host network** — GDM/DLNA/remote access require host networking.

## Contributing

See [CLAUDE.md](CLAUDE.md) for development guidelines.

## License

MIT — see [LICENSE](LICENSE). Third-party images/services keep their own licenses.
