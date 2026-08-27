# arr-dashboard

Media operations dashboard — queue, calendar, history, TRaSH Guides, library cleanup,
auto-hunting, Plex analytics.

| | |
|---|---|
| **Image** | `khak1s/arr-dashboard:latest` |
| **Port** | 41789 (host) → 3000 |
| **Network** | `bearcave` |
| **Data** | named volume `arr-dashboard-data` (`/config`, SQLite) |

## Role

The media-ops surface:

- Unified queue/calendar/history across Radarr + Sonarr
- Library management + global search via Prowlarr
- Plex analytics: now playing, on deck, watch history, statistics
- Seerr integration: requests, users, issues
- TRaSH Guides: quality profiles, custom formats, naming schemes
- Library cleanup (rule-based), auto-hunting, auto-tagger
- Notifications: Discord, Telegram, email, push

## Environment variables

| Variable | Purpose |
|----------|---------|
| `PUID` / `PGID` | Ownership of `/config` |
| `DATABASE_URL` | `file:/config/prod.db` |
| `SESSION_TTL_HOURS` | 24 |
| `LOG_LEVEL` | info |

## First-run

1. Open `https://arr.HOST_IP.nip.io` (or `http://HOST_IP:41789`)
2. Create the admin account
3. Add Radarr/Sonarr/Prowlarr instances in Settings
4. Optionally connect Plex via OAuth
