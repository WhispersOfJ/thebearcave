# Fish Functions — API-backed CLI

Terminal commands for the Bear Cave media stack. Every command calls the
target service's API directly via curl and prints human-readable text.

## Setup

1. Set fish universal variables:
```fish
set -U MEDIA_STACK_HOST_IP "192.0.2.1"
set -U MEDIA_STACK_DIR "/home/bear/TheBearCave"
set -U MEDIA_STACK_COLOR true  # optional: colored output
```

2. Install:
```bash
services/fish-functions/scripts/install.sh
```

3. Restart fish or `source ~/.config/fish/config.fish`.

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

Each function calls a service-specific helper (`__arr_api`, `__plex_api`,
`__nzbdav_api`, `__watchstate_api`) which uses curl to hit the service
API directly. No backend proxy — functions talk to services on the
`bearcave` Docker network. Color is enabled by default.
