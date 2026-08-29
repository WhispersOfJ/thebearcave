# Migrating from metacacharr

> **Historical** — this merge completed 2026-08-26 (see [HISTORY.md](../../HISTORY.md#pre-merge-history)).
> Kept for reference if the migration ever needs to be re-run.

The Metacache service from the metacacharr repo is now **built from source inside**
The Bear Cave at `services/metacache/`. If you ran Metacache standalone, here's how
to carry its cache over.

---

## What changes

| | metacacharr (standalone) | The Bear Cave |
|---|---|---|
| Location | its own repo + Docker build | `services/metacache/` (build context) |
| Image | `ghcr.io/whispersofj/metacacharr` | built locally |
| Data path | configurable (`Metacache__DataPath`) | `data/metacache/metacache.db` |
| Image cache | configurable | `data/metacache/images/` |
| Auth | `Metacache__Auth__ApiKey` | `METACACHE_API_KEY` |

The container image **runs as non-root** (`APP_UID`). If your old deployment used a
root-created named volume, fix ownership once:

```bash
docker run --rm -v metacache-data:/data alpine chown -R 1654:1654 /data
```

---

## Copying the cache (optional but smart)

The cache is regenerable via `POST /warm/all`, but copying it avoids a full warm cycle
(which can take a while on a large library and burns rate-limit budget):

```bash
# From the old data dir (or volume):
cp -a <old>/metacache.db /home/bear/TheBearCave/data/metacache/
cp -a <old>/images     /home/bear/TheBearCave/data/metacache/ 2>/dev/null || true
chown -R 1654:1654 /home/bear/TheBearCave/data/metacache
```

Then rebuild + start:

```bash
cd /home/bear/TheBearCave
docker compose up -d --build metacache
curl -s localhost:8765/metrics    # hit rate should be high immediately
```

---

## Re-adding to Plex

If Plex already has the provider registered with the same URL, nothing to do. If the
host/IP changed, update the provider URL in Plex (Settings → Metadata Agents).

---

## If you skip the copy

```bash
docker compose up -d --build metacache
curl -s -X POST localhost:8765/warm/all      # rebuild the cache from Radarr/Sonarr
```

---

## What stays in archive

The original repo's `DESIGN.md`, tests, and standalone monitoring stack are preserved
at `archive/metacacharr/` for reference. The standalone `monitoring/docker-compose.yml`
is **not** used — The Bear Cave's own monitoring stack (Prometheus/Grafana/Loki) scrapes
Metacache's `/metrics/prometheus` endpoint instead.
