# InfiniDysk (NzbDAV)

InfiniDysk is the only downloader. It retrieves Usenet content, exposes a SABnzbd-
compatible API, and serves the remote tree over WebDAV.

| | |
|---|---|
| Image | `ghcr.io/infinidysk/infinidysk` (digest-pinned) |
| Port | 3000 |
| Network | `bearcave` |
| Config | `config/nzbdav/` |
| Depends on | Prowlarr healthy |
| Healthcheck | `curl -fsSL http://localhost:3000/healthz` |

## Active configuration

The Compose environment supplies the API key, WebDAV credentials, Usenet providers,
Radarr/Sonarr instances, repair settings, Prowlarr sync, queue workers, caches, and
watchtower/preflight settings. Repair health checks are capped at 24 concurrent
operations to avoid a remote-request stampede during Plex scans. The container has a
2.5 GiB memory cap and 2 CPU quota for concurrent provider/WebDAV work. Do not replace
the `NZBDAV_CONFIG__*` block with only `WEBDAV_USERNAME`/`WEBDAV_PASSWORD`; those
names do not configure this image.

Important values:

- `FRONTEND_BACKEND_API_KEY`: shared SABnzbd-compatible API key
- `NZBDAV_WEBDAV_USER/PASS`: WebDAV credentials used by rclone
- `NZBDAV_RCLONE_RC_PASS`: rclone remote-control password
- `NZBDAV_USENET_*`: provider credentials — `NZBDAV_USENET_*` (primary),
  `NZBDAV_USENET_BACKUP_*` (backup), and `NZBDAV_USENET_EWEKA_*` (third
  slot, news.eweka.nl over SSL). All are injected into InfiniDysk's
  `NZBDAV_CONFIG__USENET__PROVIDERS` JSON in Compose.
- `NZBDAV_PROFILE_TOKEN`: profile/watchtower token

## Queue safety

The queue is not persistent across container recreation. Always check it first:

```bash
KEY=$(grep '^FRONTEND_BACKEND_API_KEY=' .env | cut -d= -f2)
python3 scripts/check_nzbdav_queue.py --api-key "$KEY"
```

Use `scripts/update-nzbdav.sh` for updates. `--force` is only for knowingly accepting
queued-NZB loss.

## Troubleshooting

```bash
curl -sf http://localhost:3000/healthz
docker compose logs --tail=100 nzbdav
docker exec nzbdav_rclone rclone lsd nzbdav: --config /config/rclone/rclone.conf
```
