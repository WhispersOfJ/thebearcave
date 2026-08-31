# Fish Functions — API-backed CLI

The fish functions are the operational surface for the eight-service media stack.
They call the host-published APIs directly; no proxy or dashboard container is required.

## Layout

```text
services/fish-functions/
├── functions/
│   ├── __arr_api.fish       # Radarr/Sonarr helper
│   ├── __plex_api.fish      # Plex helper
│   ├── __nzbdav_api.fish    # NzbDAV SABnzbd API helper
│   ├── __cli_format.fish    # Shared formatting helpers
│   └── stack-*.fish         # User-facing commands
├── completions/
└── scripts/install.sh
```

## Function categories

| Category | Purpose | Examples |
|---|---|---|
| Arr | Backlog, queue, search, and import diagnostics | `stack-arr-backlog`, `stack-arr-missing-aired` |
| Plex | Sessions, scans, trash, and maintenance | `stack-plex scan`, `stack-plex-sessions`, `stack-plex-image-clean` |
| NzbDAV | Queue, history, and failure management | `stack-nzbdav-queue`, `stack-nzbdav-history` |
| Docker/host | Status, resource usage, mounts, and logs | `stack-status`, `stack-top`, `stack-mount-health` |
| Seerr | Request visibility | `stack-seerr-requests` |

## Setup

```bash
services/fish-functions/scripts/install.sh
```

Restart fish after installation. The installer loads `.env` into the fish environment
so commands can use `RADARR_API_KEY`, `SONARR_API_KEY`, `PROWLARR_API_KEY`, `PLEX_TOKEN`,
`FRONTEND_BACKEND_API_KEY`, and the service URL overrides.

Functions target the direct host ports by default:

- Prowlarr `localhost:9696`
- Radarr `localhost:7878`
- Sonarr `localhost:8989`
- NzbDAV `localhost:3000`
- Seerr `localhost:5055`
- Plex `localhost:32400`

## ImageMaid cache cleanup

`stack-plex-image-clean` starts the profile-gated ImageMaid maintenance service. It removes
only generated Plex `Cache/PhotoTranscoder` files and prints ImageMaid's `Space Recovered:`
line. It does not resize or recompress artwork and does not remove metadata, empty trash,
clean bundles, or optimize the database. Run it only while Plex is idle; see
[ImageMaid maintenance](imagemaid.md).

## Safety behavior

The `docker` wrapper routes NzbDAV and `nzbdav_rclone` state-changing operations through
`scripts/nzbdav-safe-recreate.sh`. It blocks recreation when queued NZBs are present;
`--force` is explicit and dangerous because queued items are lost.

## Completion checks

Completions are generated from the function definitions:

```fish
fish services/fish-functions/scripts/gen-completions.fish --check
bash tests/fish/test_fish_functions.sh --offline
```

## Troubleshooting

- Connection refused: run `docker compose ps` and `stack-status`.
- Unauthorized: verify `.env` API keys and the app's stored key.
- Red Plex trash cans: run `stack-mount-health`, restore the FUSE mount, then run
  `stack-plex scan`; do not empty trash while the mount is unavailable.
