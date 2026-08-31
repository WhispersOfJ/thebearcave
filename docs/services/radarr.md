# Radarr

Radarr manages the movie library in the eight-service stack.

| | |
|---|---|
| Image | `ghcr.io/hotio/radarr:release-6.3.0.10514` |
| Port | 7878 |
| Network | `bearcave` |
| Config | `config/radarr/` |
| Depends on | `nzbdav_rclone` healthy, with restart cascade |

## Paths

| Host path | Container path |
|---|---|
| `config/radarr/` | `/config` |
| `media/movies/` | `/data/movies` |
| `/mnt/remote/nzbdav` | `/mnt/remote/nzbdav` with `rslave` propagation |

The movie root is `/data/movies`; this must match the existing Radarr database.

## Download client

Configure InfiniDysk as a SABnzbd-compatible client:

- Host: `nzbdav`
- Port: `3000`
- API key: `FRONTEND_BACKEND_API_KEY`
- Root folder: `/data/movies`

Prowlarr supplies indexers. Unpackerr watches the Radarr queue and extracts completed
archives before import.

## Stability notes

Radarr has a 1536 MiB memory cap because its database contains large MediaInfo blobs.
Keep quality profiles intact; an orphaned quality-profile reference can make the entire
movie API return HTTP 500. If that happens, inspect the database backup before editing it.

If imports fail, check the FUSE mount before changing Radarr paths:

```bash
docker exec nzbdav_rclone mountpoint -q /mnt/remote/nzbdav
docker compose logs --tail=100 radarr nzbdav unpackerr
```
