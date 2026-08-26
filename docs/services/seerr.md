# Seerr

Request manager — the "I want this" front door for your household.

| | |
|---|---|
| **Image** | `ghcr.io/seerr-team/seerr` (digest-pinned) |
| **Port** | 5055 |
| **Network** | `bearcave` |
| **Healthcheck** | `wget -qO- http://localhost:5055/api/v1/status` |
| **Config** | `config/seerr/` (gitignored) |

## Role

- Household users request movies/TV shows
- Auto-approval (or manual review) sends the title to Radarr/Sonarr
- Plex users/groups determine who can request what

## First-run

1. Open `https://seerr.HOST_IP.nip.io`
2. Complete the setup wizard
3. Connect Plex (for users), Radarr, Sonarr
4. Set request permissions per user/group

## Notes

- The image is digest-pinned because upstream's tagged releases lag `:latest` —
  bump the digest deliberately when a new tagged release exists
- Requests flow Seerr → Radarr/Sonarr → Prowlarr → InfiniDysk automatically

## Troubleshooting

- **"No users found"** — Plex connection broken; re-check Plex URL + token in Seerr settings
- **Request accepted but nothing downloads** — check the Radarr/Sonarr queue and
  InfiniDysk's queue; the download client may be misconfigured (host `nzbdav`, port 3000)
