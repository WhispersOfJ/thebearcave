# Sonarr

Sonarr manages the TV library in the eight-service stack.

| | |
|---|---|
| Image | `ghcr.io/hotio/sonarr:release-4.0.19.2979` |
| Port | 8989 |
| Network | `bearcave` |
| Config | `config/sonarr/` |
| Depends on | `nzbdav_rclone` healthy, with restart cascade |

## Paths

| Host path | Container path |
|---|---|
| `config/sonarr/` | `/config` |
| `media/shows/` | `/data/shows` |
| `/mnt/remote/nzbdav` | `/mnt/remote/nzbdav` with `rslave` propagation |

The TV root is `/data/shows`; this must match the existing Sonarr database.

## Download client

Configure InfiniDysk as a SABnzbd-compatible client:

- Host: `nzbdav`
- Port: `3000`
- API key: `FRONTEND_BACKEND_API_KEY`
- Root folder: `/data/shows`

Prowlarr supplies indexers. Unpackerr watches Sonarr’s queue and extracts completed
archives before import.

If imports fail, verify the FUSE mount first:

```bash
docker exec nzbdav_rclone mountpoint -q /mnt/remote/nzbdav
docker compose logs --tail=100 sonarr nzbdav unpackerr
```
