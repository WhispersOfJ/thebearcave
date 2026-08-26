# Prowlarr

Indexer manager — the single source of indexers for Radarr, Sonarr, and InfiniDysk.

| | |
|---|---|
| **Image** | `ghcr.io/hotio/prowlarr:release` |
| **Port** | 9696 |
| **Network** | `bearcave` |
| **Healthcheck** | `curl -sf http://localhost:9696/ping` |
| **Config** | `config/prowlarr/` (gitignored) |

## Role

- Manages all Usenet indexer connections (API keys, categories, quotas)
- Pushes indexers to Radarr/Sonarr (pull-sync) and to InfiniDysk's own search subsystem
- Everything in the stack searches through Prowlarr — no app talks to indexers directly

## Key integrations

| Consumer | How it connects |
|----------|----------------|
| Radarr / Sonarr | Prowlarr push-sync keeps indexers in sync |
| InfiniDysk | `NZBDAV_CONFIG__PROWLARR__URL` + `PROWLARR_API_KEY`, synced every 60 min |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `PROWLARR_API_KEY` | API key (generated on first boot, copy into `.env`) |

## First-run

1. Open `https://prowlarr.HOST_IP.nip.io`
2. Add your indexers (Settings → Indexers → Add Indexer)
3. Copy the generated API key into `.env` as `PROWLARR_API_KEY`
4. `docker compose up -d --force-recreate prowlarr`
5. In Radarr/Sonarr, set Prowlarr as the indexer source (Settings → Indexers)

## Troubleshooting

- **No results anywhere** — check indexer quota/grabs per indexer (Settings → Indexers →
  the indexer → History). This stack shares one 50-grabs/day cap across Sonarr/Radarr
  and InfiniDysk's watchdog/preflight.
- **"Indexer unavailable"** — indexer login expired; re-validate credentials in Prowlarr.
