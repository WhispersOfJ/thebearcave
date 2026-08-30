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
| `stack-watchstate-status` | WatchState sync state |
| `stack-help` | List all commands |

Run `stack-help` for the full list.

Tab completions are generated for every command (descriptions, positional
choices like `radarr|sonarr`, butler task names, `-y` flags, docker container
names). Regenerate after changing a function:

```fish
fish scripts/gen-completions.fish            # regenerate completions/
fish scripts/gen-completions.fish --check    # verify completions/ is current
```

## Architecture

```
functions/          # One .fish file per command
completions/        # Tab completions — GENERATED via scripts/gen-completions.fish
scripts/            # install.sh, uninstall.sh, gen-completions.fish
```

Each function calls a service-specific helper (`__arr_api`, `__arr_api_url`,
`__arr_api_key`, `__plex_api`, `__nzbdav_api`, `__watchstate_api`) which uses
curl to hit the service API directly. No backend proxy. The shared `fmt_*`
formatting helpers in `__cli_format.fish` load via `conf.d` at fish startup.
