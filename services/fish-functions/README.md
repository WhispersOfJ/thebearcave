# Fish Functions — API-backed CLI

Terminal commands for the Bear Cave media stack. Every command calls the
target service's API directly via curl and prints human-readable text.

## Setup

1. Install:
```bash
services/fish-functions/scripts/install.sh
```

2. Restart fish (or open a new terminal).

`install.sh` writes a `conf.d/bearcave-env.fish` entry that loads the repo's
`.env` into the fish environment at every startup, so API keys
(`RADARR_API_KEY`, `SONARR_API_KEY`, `PLEX_TOKEN`, …) are available without
exporting them by hand. Explicit exports still win — the loader only sets
variables that are not already set. Optional: force color on/off (default:
auto-detect TTY):
```fish
set -U STACK_COLOR true
```

Defaults target the host-published `localhost` ports (these are host-shell
tools); override with `<APP>_URL` / `PLEX_URL` env vars if needed.

## Commands

| Command | Description |
|---------|-------------|
| `stack-status` | Live state/health of every container |
| `stack-container <restart\|stop\|start> <name>` | Control a single container |
| `stack-restart-all [-y]` | Restart the whole stack |
| `stack-arr <radarr\|sonarr> <cmd>` | Trigger arr command |
| `stack-queue-status` | Live queue with speed/ETA |
| `stack-nzbdav-queue` | NzbDAV download queue |
| `stack-plex-sessions` | Who is watching what |
| `stack-plex-image-clean` | Remove generated Plex PhotoTranscoder cache and print reclaimed space |
| `stack-radarr-health` | Check Radarr DB integrity (orphaned quality profiles + size bloat) |
| `stack-help` | List all commands |

Run `stack-help` for the full list.

For manual Plex cache maintenance, run `stack-plex-image-clean`. It starts the profile-gated
ImageMaid service, removes only generated PhotoTranscoder cache files, and prints the
`Space Recovered:` amount. It does not resize artwork or perform other Plex maintenance.
Run it while Plex is idle.

Tab completions are generated for every command (descriptions, positional
choices like `radarr|sonarr`, butler task names, `-y` flags, docker container
names). Regenerate after changing a function:

```fish
fish scripts/gen-completions.fish            # regenerate completions/
fish scripts/gen-completions.fish --check    # verify completions/ is current
```

## Guarded docker compose

`docker compose up -d nzbdav` / `restart nzbdav` recreates the container and
wipes the non-persistent queue (landmine #3). After `install.sh`, a fish
function (`functions/docker.fish`) and a bash/zsh snippet
(`~/.config/bearcave/docker-guard.sh`) intercept `docker compose` so any
state-mutating op targeting nzbdav routes through
`scripts/nzbdav-safe-recreate.sh`, which runs the queue guard first and
refuses when queued NZBs would be lost. Queries (`ps`, `logs`, `config`,
`exec`) pass through ungated; `--force` skips the guard (DANGEROUS).

- **fish**: automatic after `install.sh` + restart (the function shadows the
  `docker` binary for the `compose` subcommand only).
- **bash/zsh**: source the snippet from `~/.bashrc` or `~/.zshrc`:
  ```bash
  source ~/.config/bearcave/docker-guard.sh
  ```
- Disable for one session: fish `functions -e docker`; bash `unset -f docker`.

## Architecture

```
functions/          # One .fish file per command
completions/        # Tab completions — GENERATED via scripts/gen-completions.fish
scripts/            # install.sh, uninstall.sh, gen-completions.fish
```

Each function calls a service-specific helper (`__arr_api`, `__arr_api_url`,
`__arr_api_key`, `__plex_api`, `__nzbdav_api`) which uses
curl to hit the service API directly. No backend proxy. The shared `fmt_*`
formatting helpers in `__cli_format.fish` load via `conf.d` at fish startup.
