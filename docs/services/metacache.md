# Metacache

Custom Plex metadata provider — caches TMDB/TVDB metadata locally so Plex refreshes
hit the LAN instead of the internet. Built from source.

| | |
|---|---|
| **Source** | `services/metacache/` (.NET 10, C#) |
| **Build** | `docker compose build metacache` |
| **Port** | 8765 |
| **Network** | `bearcave` |
| **Healthcheck** | `curl -sf http://localhost:8765/healthz` |
| **Data** | `data/metacache/` (SQLite DB + image cache) |
| **Depends on** | (none — but warms from Radarr/Sonarr) |

## Role

- Implements Plex's **Custom Metadata Provider** API (PMS 1.43+)
- Caches TMDB (primary) + TVDB (fallback) metadata with TTLs, ETag revalidation,
  stale-if-error, and 429 retry-with-backoff
- Rewrites artwork URLs to `http://HOST_IP:8765/img/{hash}` — Plex never fetches art
  from the internet
- Warms itself from Radarr/Sonarr libraries (nightly + on-import webhooks + predictive
  on playback start)

## Key endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /movie`, `GET /tv` | Provider definitions (Plex "Add Provider") |
| `POST /library/metadata/matches` | Match/search (Plex) |
| `GET /library/metadata/{ratingKey}` | Metadata, incl. seasons/episodes |
| `GET /img/{hash}` | Locally-cached artwork |
| `POST /warm/movies`, `/warm/shows`, `/warm/all` | Pre-populate cache |
| `POST /webhook/radarr`, `/webhook/sonarr` | Event-driven warm on import |
| `POST /webhook/plex` | Predictive warm on playback start |
| `GET /dashboard` | Interactive dashboard |
| `GET /metrics/prometheus` | Prometheus scrape endpoint |
| `GET /healthz` | Liveness |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `TMDB_KEY` | TMDB API Read Access Token (required) |
| `TVDB_KEY` | TVDB v4 key (optional, episode fallback) |
| `RADARR_API_KEY` / `SONARR_API_KEY` | Warm sources |
| `METACACHE_API_KEY` | Bearer auth for `/admin/*`, `/webhook/*`, `POST /warm/*` |
| `WARM_LANG_0` | First language to warm (default `en-US`) |

## Registering in Plex

1. Settings → Metadata Agents → **Add Provider** → `http://HOST_IP:8765/movie`
2. Repeat with `http://HOST_IP:8765/tv`
3. **Add Agent**, name it, set Metacache as **Primary** for a library
4. Assign that library to use the agent

The provider API itself is unauthenticated (Plex doesn't send auth yet) — keep it
LAN-only. `METACACHE_API_KEY` locks down the write endpoints.

## Troubleshooting

- **Plex shows "Fix Match" for everything** — warm the cache first
  (`POST /warm/all`), then refresh metadata in Plex
- **Artwork missing** — check `data/metacache/images/` growth and the total cap;
  images evict oldest-first when over budget
- **Rate-limited during first warm** — single-flight + backoff should absorb it; warm
  off-peak for very large libraries
- **Stale metadata** — cache TTLs (search 12 h, details 24 h); purge selectively from
  the dashboard or `POST /admin/purge/selective`
