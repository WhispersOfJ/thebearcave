# Bazarr

Bazarr is the subtitle companion to Sonarr and Radarr: it watches both libraries,
searches subtitle providers, and downloads subtitles next to the media files.

| | |
|---|---|
| Image | `ghcr.io/hotio/bazarr:release-1.6.0` |
| Port | 6767 |
| Network | `bearcave` |
| Config | `config/bazarr/` |
| Healthcheck | `curl http://localhost:6767/ping` (unauthenticated) |
| Memory cap | 768m, 1 CPU (174 MiB steady-state observed on this host) |

Access it directly at `http://HOST_IP:6767`; no reverse proxy is deployed.

## History

Retired in the 2026-08-30 slim-down after crash-looping OOM at a 128m cap, then
re-adopted 2026-09-03 as a fresh implementation (see
[lifecycle.md](lifecycle.md) for both records).

## Integration contract

- **Connections are configured once in the web UI** (Settings → Sonarr /
  Settings → Radarr, using `http://sonarr:8989` / `http://radarr:7878` and each
  app's API key from `.env`). Bazarr has **no environment-variable settings
  surface** — unlike Sonarr/Radarr there is no declarative bootstrap, so the
  one-time UI setup is part of the deployment checklist.
- **Path parity with the *arr apps**: Bazarr mounts exactly what Sonarr and
  Radarr mount — `/mnt/remote/nzbdav` (the streamed library), `/data/shows`,
  and `/data/movies` — so Sonarr/Radarr path configuration works unchanged and
  no path mapping is needed.
- **Read-only over the media trees**: the FUSE mount and media dirs are bound
  `:rslave`; Bazarr only writes subtitle files beside the media. It depends on
  `sonarr`/`radarr` health but **deliberately not** on `nzbdav_rclone` — it
  keeps running through mount-owner restarts and NzbDAV recreations (landmines
  #2/#4 in AGENTS.md do not apply to it).
- **Auth**: API-key family like the *arr apps — `X-Api-Key` header, key in
  `config/bazarr/config/config.ini`. The repo's scripts call no Bazarr
  endpoints today; the healthcheck uses the unauthenticated `/ping`.

## Operational notes

- The 128m cap that killed the pre-slim instance was ~8× under its real
  footprint; 768m leaves the same headroom ratio as the other *arr apps. If it
  ever grows, the same `check_radarr_db_size.py`-style gate pattern applies —
  Bazarr's SQLite lives at `config/bazarr/db/bazarr.db`.
- Subtitle searches fan out to external providers; the 1 CPU quota keeps a mass
  search from starving the other services.
