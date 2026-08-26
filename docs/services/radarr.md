# Radarr

Movie management — the movie half of the *arr pair.

| | |
|---|---|
| **Image** | `ghcr.io/hotio/radarr:release` |
| **Port** | 7878 |
| **Network** | `bearcave` |
| **Healthcheck** | `curl -sf http://localhost:7878/ping` |
| **Config** | `config/radarr/` (gitignored) |
| **Depends on** | `nzbdav_rclone` healthy (restart cascade) |

## Role

- Tracks the movie library (15,000+ titles), including anime movies (folded in via
  genre/tag routing — no separate instance)
- Searches via Prowlarr, grabs through InfiniDysk's SABnzbd-compatible API
- Imports via symlinks into the FUSE mount (`/mnt/remote/nzbdav/completed-symlinks`)

## Volume mounts

| Host path | Container path | Purpose |
|-----------|----------------|---------|
| `config/radarr/` | `/config` | App state |
| `/mnt/remote/nzbdav` | `/mnt/remote/nzbdav` (rslave) | FUSE mount for symlink imports |
| `media/movies/` | `/data/movies` | Movie root folder |
| `media/anime-movies/` | `/data/anime-movies` | Anime movie root folder |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `RADARR_API_KEY` | API key (generated on first boot, copy into `.env`) |

## First-run

1. Open `https://radarr.HOST_IP.nip.io`
2. Download client → Add → **InfiniDysk**: host `nzbdav`, port 3000,
   API key = `FRONTEND_BACKEND_API_KEY` from `.env`
3. Root folders: `/data/movies`, `/data/anime-movies`
4. Copy the generated API key into `.env`, `docker compose up -d --force-recreate radarr`
5. Indexers arrive automatically via Prowlarr push-sync

## Troubleshooting

- **Imports failing with I/O errors** — the FUSE mount may be down. Check
  `docker exec nzbdav_rclone mountpoint -q /mnt/remote/nzbdav`; restart dependents after.
- **Queue stuck on "importing"** — files may be broken or the mount stale. Use Control
  Panel's queue tools or check `docker compose logs radarr`.
- **API key changed** — every consumer (Control Panel, InfiniDysk, Unpackerr, Metacache)
  reads `RADARR_API_KEY`; update `.env` and `--force-recreate` the consumers.
