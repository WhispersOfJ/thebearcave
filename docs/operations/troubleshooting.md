# Troubleshooting

Start with the first unhealthy component in dependency order. The active stack is:
Prowlarr → NzbDAV → rclone FUSE mount → Radarr/Sonarr/Plex/Unpackerr, with Seerr
providing requests.

## Everything is unhealthy

```bash
docker compose ps
docker compose config --quiet
df -h
```

Check the first failure in this order:

1. `prowlarr` and `nzbdav` healthchecks
2. `nzbdav_rclone` mount health
3. Radarr/Sonarr/Plex/Unpackerr
4. Seerr

## Plex shows red trash cans or missing files

This is usually a scan performed while the FUSE mount was unavailable. Do not empty
trash or rescan until the mount is healthy:

```bash
docker exec nzbdav_rclone mountpoint -q /mnt/remote/nzbdav
docker exec nzbdav_rclone ls /mnt/remote/nzbdav | head
```

Recovery:

```bash
docker compose restart nzbdav nzbdav_rclone
# Wait for the mount healthcheck, then restart consumers.
docker compose restart radarr sonarr plex unpackerr
# Trigger a Plex library scan, then empty trash only after expected files reappear.
```

## Mount gone while the container is Up

The rclone process can fail between Docker restarts. The mountpoint check is authoritative:

```bash
docker inspect --format '{{.State.Health.Status}}' nzbdav_rclone
docker logs --tail=100 nzbdav_rclone
```

The rclone entrypoint clears stale FUSE state before mounting. If it still loops, check
for stale host mounts and follow the FUSE recovery procedure in
[docs/services/nzbdav-rclone.md](../services/nzbdav-rclone.md).

## NzbDAV returns 401

Verify both the running environment and the client key:

```bash
docker exec nzbdav env | grep FRONTEND_BACKEND_API_KEY
grep '^FRONTEND_BACKEND_API_KEY=' .env
```

Radarr and Sonarr must use the same value as `FRONTEND_BACKEND_API_KEY`. NzbDAV’s WebDAV
remote uses the credentials in `config/nzbdav-rclone/rclone.conf`.

## NzbDAV queue is not accessible

```bash
KEY=$(grep '^FRONTEND_BACKEND_API_KEY=' .env | cut -d= -f2)
curl -s "http://localhost:3000/api?mode=queue&output=json&apikey=$KEY"
```

Do not recreate NzbDAV while the queue is unknown. Use
`scripts/check_nzbdav_queue.py` or the guarded update script first.

## Radarr/Sonarr imports are stuck

```bash
docker compose logs --tail=100 radarr sonarr nzbdav unpackerr
docker exec nzbdav_rclone ls /mnt/remote/nzbdav/completed-symlinks | head
```

Confirm the download client is `nzbdav:3000`, the API key matches, the FUSE mount is
healthy, and the root folders are `/data/movies` and `/data/shows`.

## Seerr requests do not download

Check Seerr’s connections to Plex, Radarr, and Sonarr, then inspect the relevant *arr
queue and NzbDAV queue. Seerr itself should respond at `http://HOST_IP:5055`.

## Hardware transcoding falls back to software

```bash
docker exec plex ls -l /dev/dri
```

Plex Pass, GPU drivers, `/dev/dri`, and hardware acceleration in Plex settings are
required. Library scans still use CPU even when playback uses VAAPI.

## Container will not stop

Plex has a required 90-second grace period. Give it time before escalating:

```bash
docker stop -t 90 plex
```

For a wedged FUSE handle, restore/restart the mount owner first, then restart consumers.

## Escalation order

1. `docker compose ps`
2. Check the NzbDAV queue before any recreate.
3. Check the FUSE mount before any Plex scan.
4. Inspect logs for the first unhealthy service.
5. Restore from backup before destructive cleanup; see
   [backup & restore](backup-restore.md).
