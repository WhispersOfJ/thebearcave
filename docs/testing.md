# Testing

How to verify the stack is actually working — automated checks, integration pipeline,
and manual live tests.

---

## Automated health checks (all 22 services)

```bash
./tests/health/run-all.sh                # everything
./tests/health/run-all.sh --service plex # one service
./tests/health/run-all.sh --verbose
```

Checks each container:
- exists + running (`docker inspect`)
- Docker health status (`healthy` / `no_healthcheck`)

Exit code 0 = all pass.

---

## Integration pipeline test

```bash
./tests/integration/test_pipeline.sh
./tests/integration/test_pipeline.sh --dry-run   # prereqs only
```

Covers the real data path:

| Check | What it verifies |
|-------|------------------|
| Infra readiness | Docker, Plex/Radarr/Sonarr/nzbdav containers up |
| FUSE mount | `mountpoint -q` on nzbdav_rclone + content present |
| rclone RC | `:5572/core/stats` responds |
| Plex library | sections exist, items present |
| Radarr root folders | `/api/v3/rootfolder` configured |
| Sonarr root folders | `/api/v3/rootfolder` configured |
| InfiniDysk API | `/healthz` + queue endpoint |
| Metacache | `/healthz` + metrics |
| Symlink integrity | no broken symlinks in `media/*` |

Requires `.env` loaded (real API keys) and the stack up.

---

## Unit tests

### Control Panel (Django)

```bash
cd services/control-panel/django
CONTROL_PANEL_SECRET_KEY=ci-test-secret pytest
```

### Metacache (.NET)

```bash
cd services/metacache
dotnet test Metacache.slnx
```

### nzbdav-exporter

```bash
cd services/nzbdav-exporter
python -m pytest test_exporter.py -v
```

---

## Live tests (manual, the ones that actually matter)

### InfiniDysk streaming

```bash
# 1. Queue is alive
curl -s http://HOST_IP:3000/healthz

# 2. WebDAV is readable through the FUSE mount
docker exec nzbdav_rclone find /mnt/remote/nzbdav -maxdepth 2 | head

# 3. Stream a file end-to-end (no local disk involvement)
docker exec nzbdav_rclone dd if=/mnt/remote/nzbdav/completed-symlinks/<show>/<ep>.mkv \
  of=/dev/null bs=1M count=64
# ~64MB streamed without error = the WebDAV→FUSE→read path works
```

### Plex playback

```bash
# 1. Server identity
curl -s http://HOST_IP:32400/identity

# 2. A library item plays (direct + transcode)
#    Open a title in the Plex web app. Force a transcode and confirm:
#    - playback starts without buffering loops
#    - the transcode uses HW (Plex web UI → Now Playing shows "Transcode (HW)")
#    - seeking/rewind is responsive (segment cache)

# 3. API-level: list recent sessions to confirm playback registered
curl -s "http://HOST_IP:32400/status/sessions" -H "X-Plex-Token: $PLEX_TOKEN"
```

### Metacache serving Plex

```bash
# 1. Provider registered in Plex (see services/metacache.md)
# 2. Warm the cache, then:
curl -s "http://HOST_IP:8765/library/metadata/tmdb-movie-105" | head
# 3. Confirm Plex refreshes from the LAN: watch Metacache logs during a Plex refresh —
#    cache hits, not upstream calls
```

### Traefik routing

```bash
for svc in panel arr radarr sonarr prowlarr seerr nzbdav metacache watchstate grafana; do
  curl -sk -o /dev/null -w "%{http_code} $svc\n" "https://$svc.$HOST_IP.nip.io/"
done
```

---

## When to run what

| Moment | Run |
|--------|-----|
| After any compose change | `docker compose config --quiet` + health checks |
| Before merging a PR | `validate.yml` CI (compose, shellcheck, ruff, Django tests) |
| After touching the FUSE mount | integration pipeline + a Plex playback test |
| After restoring from backup | full health + integration + live tests |
| Nightly (CI) | compose validation, Dockerfile builds, script syntax, yaml lint |
