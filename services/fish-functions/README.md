# Fish Functions — API-backed CLI

Terminal commands for the Bear Cave media stack. Every command calls the
target service's API directly via curl and prints human-readable text.

## Setup

1. Export the API keys the functions read (e.g. from `.env`):
```fish
set -x RADARR_API_KEY ...
set -x SONARR_API_KEY ...
set -x PLEX_TOKEN ...
```
Optional: force color on/off (default: auto-detect TTY):
```fish
set -U STACK_COLOR true
```

2. Install:
```bash
services/fish-functions/scripts/install.sh
```

3. Restart fish or `source ~/.config/fish/config.fish`.

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

## Architecture

```
functions/          # One .fish file per command
completions/        # Manual tab completions
scripts/            # install.sh, uninstall.sh
```

Each function calls a service-specific helper (`__arr_api`, `__arr_api_url`,
`__arr_api_key`, `__plex_api`, `__nzbdav_api`, `__watchstate_api`) which uses
curl to hit the service API directly. No backend proxy. The shared `fmt_*`
formatting helpers in `__cli_format.fish` load via `conf.d` at fish startup.
