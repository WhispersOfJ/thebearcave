# Troubleshooting

Playbooks for the failures that actually happen. Start with the symptom, follow the steps.

---

## Everything is unhealthy

```bash
docker compose ps          # which are down/unhealthy?
grep changeme .env         # placeholder values left?
docker compose config --quiet   # config still valid?
df -h                      # disk full? (Loki/Prometheus/caches)
```

Most likely causes:
1. `.env` has placeholders → fill real values, `--force-recreate`
2. FUSE mount down → everything depending on it is unhealthy
3. Port conflict (cAdvisor's 8080, etc.) → `ss -tlnp | grep <port>`

---

## Plex shows 19,000 items "deleted"

Classic FUSE-mount-death symptom:

```bash
docker exec nzbdav_rclone mountpoint -q /mnt/remote/nzbdav; echo $?   # nonzero = dead
```

Recovery:
```bash
docker compose restart nzbdav nzbdav_rclone          # mount owner first
docker compose restart radarr sonarr plex unpackerr cleanuparr  # then dependents
# Trigger a Plex rescan (web UI or API)
```

**Do not** let Plex run a full scan while the mount is down — it marks items deleted.

---

## Mount gone but container "Up"

The rclone process can crash-loop while Docker reports the container running between
restarts. The healthcheck (`mountpoint -q`) is the truth, not `docker ps`:

```bash
docker inspect --format '{{.State.Health.Status}}' nzbdav_rclone
```

If unhealthy, restart it (and dependents per the playbook above).

---

## Radarr/Sonarr imports stuck on "importing"

```bash
docker compose logs --tail=50 radarr sonarr nzbdav
docker exec nzbdav_rclone ls /mnt/remote/nzbdav/completed-symlinks | head
```

- If the symlinks dir is empty/absent → the download didn't complete or the mount is stale
- If files exist but imports hang → use Unpackerr logs or the *arr queue UI
- Confirm the download client config points at `nzbdav:3000` with the right API key

---

## Traefik routes 404 / service unreachable

```bash
docker compose ps traefik
docker logs traefik | tail -50           # routing errors show here
docker inspect <service> | grep -A3 traefik.enable
```

Common causes:
- Service missing `traefik.enable=true` (exposedByDefault is false)
- `HOST_IP` changed but the service wasn't recreated (labels are baked at create)
- nip.io DNS issue → test `dig +short panel.192.168.1.100.nip.io`

---

## Metacache "Fix Match" for everything

```bash
curl -s localhost:8765/warm/status        # is a warm running/done?
curl -s localhost:8765/metrics            # hit rate?
```

- Run `POST /warm/all` once, then refresh metadata in Plex
- Check `TMDB_KEY` is valid (bad key = every lookup fails)
- Check disk: `data/metacache/` full → images evict, metadata still fine

---

## Hardware transcode falling back to software

```bash
docker exec plex ls /dev/dri               # needs card1 + renderD128 + by-path
docker exec plex ls /dev/dri/renderD128    # world-writable check
```

- Plex Pass required; verify in Plex → Settings → Transcoder
- The **whole** `/dev/dri` must be mapped (not just renderD128)
- Intel GPU drivers on the host must expose VAAPI

---

## Container won't die (D-state hang)

Plex is the known case. Restarting the FUSE mount owner (nzbdav_rclone) is the designed
escape — it aborts the wedged FUSE connection. Manual fallback:

```bash
docker compose restart nzbdav nzbdav_rclone   # abort the mount first
docker stop -t 90 plex                          # give the grace period its due
```

---

## Secrets lost / .env deleted

If `secrets/` or `.env` vanish:

```bash
cp .env.template .env
./scripts/setup.sh --non-interactive     # regenerates secrets/ (new values!)
```

> Regenerated secrets are **new** values — every app's stored API key will mismatch
> until you copy each app's self-generated key into `.env` (Radarr/Sonarr/Prowlarr
> generate their own on boot). This is why backups matter.

---

## Grafana blank / no datasources

```bash
docker compose logs grafana | tail -30
docker exec grafana ls /etc/grafana/provisioning/datasources
```

Provisioning is bind-mounted read-only — broken YAML = silently empty dashboards.
Validate: `docker compose exec grafana cat /etc/grafana/provisioning/datasources/*.yaml`

---

## Escalation order

1. `docker compose ps` → find the first unhealthy in dependency order
2. Fix the root cause, not the symptom (a FUSE restart fixes 5 containers at once)
3. Restart dependents after mount-owner changes
4. If nothing obvious: `docker compose logs --tail=200 <service>`
5. Data loss? Stop immediately, see [Backup & Restore](backup-restore.md)
