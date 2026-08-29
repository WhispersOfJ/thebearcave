# Fish Functions — API-backed CLI

## Purpose

Terminal commands for the Bear Cave media stack. ~95 `stack-*` functions provide
operational visibility and control from the fish shell, calling each service's
API directly via curl.

## Architecture

```
services/fish-functions/
├── functions/
│   ├── __arr_api.fish          # Radarr/Sonarr API helper
│   ├── __plex_api.fish         # Plex API helper
│   ├── __nzbdav_api.fish       # NzbDAV API helper
│   ├── __watchstate_api.fish   # WatchState API helper
│   ├── __cli_format.fish       # Shared formatting (colors, status dots)
│   ├── __plex_butler.fish      # Shared Plex butler task helper
│   ├── stack-*.fish            # One file per command
│   └── __stack_arr_app.fish    # Validates arr instance name
├── completions/                # Tab completions (GENERATED — one file per command)
├── scripts/
│   ├── install.sh              # Symlink functions + completions
│   ├── uninstall.sh            # Remove symlinks
│   └── gen-completions.fish    # Regenerates completions/ from function definitions
└── README.md
```

**No backend proxy.** Each function calls its target service's API directly on
the `bearcave` Docker network — the previous central routing proxy was removed
in the Phase 2 migration.

## Function Categories

| Category | Count | Helper | Example |
|----------|-------|--------|---------|
| Arr operations | 19 | `__arr_api` | `stack-arr-backlog radarr` |
| Plex operations | 25 | `__plex_api` + `__plex_butler` | `stack-plex-sessions` |
| Docker/host | 10 | `docker ps/stats/inspect` | `stack-top --by cpu` |
| NzbDAV | 5 | `__nzbdav_api` | `stack-nzbdav-queue` |
| WatchState | 3 | `__watchstate_api` | `stack-watchstate-status` |
| Seerr | 1 | direct API | `stack-seerr-requests` |
| Ratings/external | 2 | OMDb/MDBList API | `stack-rating-imdb` |
| Letterboxd/MDBList | 10 | local file tracking | `stack-letterboxd-import` |
| Loop detection | 3 | Arr grab history | `stack-loop-candidates` |

## Setup

```fish
# Optional: force color on/off (default: auto-detect TTY)
set -U STACK_COLOR true

bash services/fish-functions/scripts/install.sh
```

### Tab completions

Every `stack-*` command ships a completion file (command description, positional
choices like `radarr|sonarr` or butler task names, `-y/--yes` flags, dynamic
docker container names, and previously-tracked list URLs for the untrack
commands). `install.sh` symlinks them into `~/.config/fish/completions/`, where
fish autoloads them by command name.

`completions/` is **generated** — never edit those files by hand. Argument
completions live in the table inside `scripts/gen-completions.fish`; descriptions
are extracted from each function's `--description`. After adding or changing a
function:

```fish
fish services/fish-functions/scripts/gen-completions.fish          # regenerate
fish services/fish-functions/scripts/gen-completions.fish --check  # CI drift gate
```

Functions read API keys from the environment (`RADARR_API_KEY`, `SONARR_API_KEY`,
`PROWLARR_API_KEY`, `PLEX_TOKEN`, `FRONTEND_BACKEND_API_KEY`, `WS_API_KEY`,
`MDBLIST_KEY`, `OMDB_KEY`, `SEERR_API_KEY`) and honor `<APP>_URL` / `PLEX_URL` /
`NZBDAV_URL` / `WATCHSTATE_URL` / `SEERR_URL` overrides.
Defaults target the host-published `localhost` ports — these are host-shell
tools; docker service names will not resolve from outside the compose network.

## Configuration

Functions read API keys from environment variables (set in `.env`):
- `RADARR_API_KEY`, `SONARR_API_KEY`, `PROWLARR_API_KEY`
- `PLEX_TOKEN`
- `NZBDAV_WEBDAV_USER`, `NZBDAV_WEBDAV_PASS`
- `WS_API_KEY`

The helper functions (`__arr_api`, etc.) are prefixed with `__` so they are
not installed as user-facing commands, but they ARE symlinked onto the function
path — the `stack-*` commands call them at runtime. `__cli_format.fish` (shared
`fmt_*` formatting helpers) is loaded via `~/.config/fish/conf.d/` because
autoload can never trigger on a file nothing invokes by name.

## Troubleshooting

- **"Connection refused"**: Service may be down. Check `stack-status`.
- **"Unauthorized"**: API key not set or wrong. Verify `.env` values.
- **Empty output**: Service returned no data (empty queue, no sessions).
- **Formatting issues**: Ensure `__cli_format.fish` is installed (it provides
  colors and status dot helpers).
