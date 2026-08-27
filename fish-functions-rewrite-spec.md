# Fish Functions Rewrite — Spec

## Overview

Complete rewrite of all ~80+ `stack-*` fish shell functions that serve as the
terminal CLI for the Bear Cave media stack. The current functions live in
`archive/media-stack/fish-functions/` (mirrored from `~/.config/fish/functions/`)
and date from the FastAPI-era control panel. This rewrite modernizes them to work
with the Django/DRF control panel, adds new CLI-oriented API endpoints, and
establishes a clean, maintainable architecture.

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Location | `services/fish-functions/` | Dedicated service directory alongside other services |
| API access | Traefik hostnames (`bearcave.HOST_IP.nip.io`) | HTTPS, works through reverse proxy, no hardcoded IPs |
| Scope | Full rewrite — all 80+ commands | Complete replacement, not incremental |
| Formatting | New `/api/v2/cli/*` endpoints | API returns pre-formatted text, fish just prints it |
| Env path | Fish universal var (`$MEDIA_STACK_DIR`) | Set once in `config.fish`, referenced everywhere |
| File structure | One `.fish` file per command | Same as today, familiar pattern |
| Completions | Manual completion files | No generator dependency, simpler to maintain |
| Backward compat | Clean break | Rename/reorganize freely — this is a rewrite |
| CLI output | Both plain text and colored (flag-controlled) | `?color=true` by default, plain with `?color=false` |
| API helper | Simplified curl (no Python) | API returns text, no JSON parsing needed |
| Tooling | Separate install + completion scripts | Independent concerns |
| Discovery | Auto-discover from files | `stack-help` scans directory, reads `--description` |

## Architecture

```
services/fish-functions/            # API-backed commands
├── functions/
│   ├── stack-status.fish
│   ├── stack-container.fish
│   ├── stack-restart-all.fish
│   ├── ...
│   ├── stack-letterboxd-import.fish   # Collapsed subcommand (list|watchlist|...)
│   ├── stack-plex-backup-database.fish # Separate per Butler task
│   ├── ...
│   └── __stack_api.fish               # Internal helper (not installed as stack-*)
├── completions/
│   ├── stack-status.fish
│   ├── stack-container.fish
│   └── ...
├── scripts/
│   ├── install.sh
│   └── uninstall.sh
└── README.md

services/host-tools/               # Local-only commands (no API)
├── functions/
│   ├── stack-disk-free.fish
│   ├── stack-kernel-check.fish
│   ├── stack-pkg-update.fish
│   ├── ...
│   └── __host_helper.fish          # Local utility functions
├── completions/
│   ├── stack-disk-free.fish
│   └── ...
├── scripts/
│   ├── install.sh
│   └── uninstall.sh
└── README.md
```

## New CLI API Endpoints

All new endpoints live under `/api/v2/cli/` and return plain text (with optional
ANSI color). They are separate from the existing JSON endpoints to keep both
interfaces clean.

### Endpoint Design

- **Base path**: `/api/v2/cli/`
- **Auth**: `X-Api-Key` header (same service key as existing endpoints)
- **Output**: Plain text by default
- **Color**: `?color=true` enables ANSI codes, `?color=false` forces plain text
- **Auto-detection**: If `Accept: text/x-terminal` header is present, enable color
- **Error format**: Plain text error message, non-zero HTTP status

### Endpoint List

#### Container & Stack Management
| Method | Path | Description | Replaces |
|--------|------|-------------|----------|
| GET | `/cli/status` | Live state/health of every container | `stack-status` |
| POST | `/cli/container/{name}/{action}` | Restart/stop/start a container | `stack-container` |
| POST | `/cli/stack/restart-all` | Restart every container (confirm gate) | `stack-restart-all` |
| GET | `/cli/resource-check` | Containers missing mem_limit/cpus | `stack-resource-check` |
| GET | `/cli/oom-check` | Containers with OOM-kill flag | `stack-oom-check` |
| GET | `/cli/image-check` | Pinned images vs registry digest | `stack-image-check` |
| GET | `/cli/top?by=cpu&limit=10` | Top containers by resource usage | `stack-top` |
| GET | `/cli/disk-usage` | Per-app config directory sizes | `stack-disk-config-sizes` |
| GET | `/cli/mount-health` | FUSE mountpoint health | `stack-mount-health` |
| GET | `/cli/perms-check` | Unreadable config files | `stack-perms-check` |
| GET | `/cli/version` | README version + container count | `stack-version` |

#### Arr App Operations
| Method | Path | Description | Replaces |
|--------|------|-------------|----------|
| POST | `/cli/arr/{app}/command/{command}` | Trigger arr command | `stack-arr` |
| GET | `/cli/arr/{app}/backlog` | Command queue backlog | `stack-arr-backlog` |
| GET | `/cli/arr/{app}/missing-aired` | Monitored + missing + aired | `stack-arr-missing-aired` |
| GET | `/cli/arr/{app}/import-candidates` | Files ready to import | `stack-arr-import-candidates` |
| POST | `/cli/arr/{app}/import/{index}` | Import one file by index | `stack-arr-import` |
| POST | `/cli/arr/{app}/import-all` | Import every candidate | `stack-arr-import-all` |
| GET | `/cli/arr/{app}/blocklist?limit=20` | Recent blocklisted releases | `stack-arr-blocklist` |
| DELETE | `/cli/arr/{app}/blocklist` | Clear all blocklisted | `stack-arr-clear-blocklist` |
| GET | `/cli/arr/{app}/recently-added?limit=10` | Recently added items | `stack-arr-recently-added` |
| GET | `/cli/arr/{app}/cutoff-unmet?limit=10` | Below quality cutoff | `stack-cutoff-unmet` |
| GET | `/cli/arr/{app}/import-lists` | Configured import lists | `stack-import-lists` |
| GET | `/cli/arr/{app}/logs?lines=100` | Tail container logs | `stack-arr-logs` |
| POST | `/cli/arr/{app}/toggle-search?enabled=true` | Toggle RSS + auto search | `stack-arr-toggle-search` |
| GET | `/cli/arr/starvation` | Import starvation diagnosis | `stack-arr-import-starvation` |
| GET | `/cli/arr/queue-errors` | Queue items flagged as problems | `stack-arr-queue-errors` |
| GET | `/cli/command-queue-summary` | Backlog across all arr apps | `stack-command-queue-summary` |
| GET | `/cli/queue/status` | Live queue with speed/ETA | `stack-queue-status` |
| GET | `/cli/backlog/status` | Wanted/missing with throughput ETA | `stack-backlog-status` |
| POST | `/cli/queue/autofix` | Auto-fix stuck queue items | `stack-queue-autofix` |

#### NzbDAV
| Method | Path | Description | Replaces |
|--------|------|-------------|----------|
| GET | `/cli/nzbdav/queue` | Current download queue | `stack-nzbdav-queue` |
| GET | `/cli/nzbdav/history?limit=20` | Recent download history | `stack-nzbdav-history` |
| GET | `/cli/nzbdav/stats` | Aggregate queue/history counts | `stack-nzbdav-stats` |
| POST | `/cli/nzbdav/delete-failures` | Delete all Failed history | `stack-nzbdav-delete-failures` |
| GET | `/cli/nzbdav/dedup-check` | Verify dedup config | `stack-nzbdav-dedup-check` |

#### Plex
| Method | Path | Description | Replaces |
|--------|------|-------------|----------|
| POST | `/cli/plex/{action}` | Trigger maintenance action | `stack-plex` |
| GET | `/cli/plex/libraries` | List library names | `stack-plex-libraries` |
| POST | `/cli/plex/empty-trash?library=...` | Empty trash | `stack-plex-empty-trash` |
| POST | `/cli/plex/analyze?library=...` | Queue deep analysis | `stack-plex-analyze` |
| GET | `/cli/plex/duplicates?min_gb=2` | Flag duplicate files | `stack-plex-duplicates` |
| GET | `/cli/plex/sessions` | Active sessions | `stack-plex-sessions` |
| GET | `/cli/plex/recently-added?limit=10` | What's visible in Plex | `stack-plex-recently-added` |
| GET | `/cli/plex/updates` | Check for Plex updates | `stack-plex-updates` |
| POST | `/cli/plex/butler/{task}` | Fire a Butler task (each also has its own fish file: `stack-plex-{task}.fish`) | `stack-plex-butler` + 20 wrappers |

#### WatchState
| Method | Path | Description | Replaces |
|--------|------|-------------|----------|
| GET | `/cli/watchstate/status` | Sync state + import schedule | `stack-watchstate-status` |
| POST | `/cli/watchstate/import` | Queue out-of-schedule import | `stack-watchstate-import-now` |
| GET | `/cli/watchstate/history?title=...&limit=20` | Watch history | `stack-watchstate-history` |

#### Cleanuparr
| Method | Path | Description | Replaces |
|--------|------|-------------|----------|
| GET | `/cli/cleanuparr/instances` | Connected arr instances | `stack-cleanuparr-instances` |
| GET | `/cli/cleanuparr/strikes?limit=15` | Recent strikes | `stack-cleanuparr-strikes` |

#### Log Levels
| Method | Path | Description | Replaces |
|--------|------|-------------|----------|
| GET | `/cli/log-levels` | Current log levels | `stack-log-levels` |
| POST | `/cli/log-levels/reset` | Reset to info | `stack-log-levels reset` |

#### Seerr
| Method | Path | Description | Replaces |
|--------|------|-------------|----------|
| GET | `/cli/seerr/requests?status=pending` | Media requests | `stack-seerr-requests` |

#### Notifications
| Method | Path | Description | Replaces |
|--------|------|-------------|----------|
| POST | `/cli/notify/test` | Send test Discord message | `stack-notify-test` |

#### Ratings (external API, not control panel)
| Method | Path | Description | Replaces |
|--------|------|-------------|----------|
| GET | `/cli/rating/imdb/{id}` | IMDb rating via OMDb | `stack-rating-imdb` |
| GET | `/cli/rating/mdblist/{id}` | MDBList score | `stack-rating-mdblist` |

#### Loop Remediation
| Method | Path | Description | Replaces |
|--------|------|-------------|----------|
| GET | `/cli/loop/candidates?app=radarr` | Titles with repeated failures | `stack-loop-candidates` |
| POST | `/cli/loop/unmonitor?app=radarr&id=123` | Unmonitor a looping item | `stack-loop-unmonitor` |
| POST | `/cli/loop/exclude?id=123` | Add to Radarr exclusions | `stack-loop-exclude` |

#### List Imports (collapsed subcommands)
| Method | Path | Description | Replaces |
|--------|------|-------------|----------|
| POST | `/cli/letterboxd/import?type=list&url=...` | Import Letterboxd content (type: list|watchlist|watched|collection|filmography|popular|random) | `stack-letterboxd-radarr-*` (7 commands → 1) |
| POST | `/cli/letterboxd/track` | Register for nightly sync | `stack-letterboxd-radarr-track` |
| DELETE | `/cli/letterboxd/track` | Unregister from sync | `stack-letterboxd-radarr-untrack` |
| GET | `/cli/letterboxd/tracked` | Lists being synced | `stack-letterboxd-radarr-tracked` |
| GET | `/cli/letterboxd/history` | Recent sync runs | `stack-letterboxd-radarr-history` |
| POST | `/cli/mdblist/import` | Import MDBList list | `stack-mdblist-import` |
| POST | `/cli/mdblist/track` | Register for nightly sync | `stack-mdblist-radarr-track` |
| DELETE | `/cli/mdblist/track` | Unregister from sync | `stack-mdblist-radarr-untrack` |
| GET | `/cli/mdblist/tracked` | Lists being synced | `stack-mdblist-radarr-tracked` |
| GET | `/cli/mdblist/history` | Recent sync runs | `stack-mdblist-radarr-history` |

#### Host System (not control panel — local commands)
These don't hit the API. They run locally on the host.

| Command | Description | Replaces |
|---------|-------------|----------|
| `stack-disk-free [warn] [crit]` | Disk free with thresholds | `stack-disk-free` |
| `stack-disk-health` | SMART health summary | `stack-disk-health` |
| `stack-mem-pressure` | Kernel PSI stats | `stack-mem-pressure` |
| `stack-kernel-check` | Running vs installed kernel | `stack-kernel-check` |
| `stack-reboot-check` | Pending reboot marker | `stack-reboot-check` |
| `stack-uptime-report` | Uptime + load + shutdown | `stack-uptime-report` |
| `stack-zombie-check` | Zombie processes | `stack-zombie-check` |
| `stack-service-failed` | Failed systemd units | `stack-service-failed` |
| `stack-timer-status` | Stack timer states | `stack-timer-status` |
| `stack-cron-list` | Timers + crontab | `stack-cron-list` |
| `stack-journal-errors` | Error journal entries | `stack-journal-errors` |
| `stack-journal-size` | Journald disk usage | `stack-journal-size` |
| `stack-firewall-status` | nftables + listening ports | `stack-firewall-status` |
| `stack-ssh-doctor` | SSH config health | `stack-ssh-doctor` |
| `stack-git-status-all` | Git status across repos | `stack-git-status-all` |
| `stack-pkg-updates` | Pending updates | `stack-pkg-updates` |
| `stack-pkg-update` | Run system update | `stack-pkg-update` |
| `stack-pkg-history` | Pacman transaction log | `stack-pkg-history` |
| `stack-pkg-orphans` | Orphaned packages | `stack-pkg-orphans` |
| `stack-pkg-clean-cache` | Vacuum package cache | `stack-pkg-clean-cache` |
| `stack-aur-audit` | AUR security audit | `stack-aur-audit` |
| `stack-flatpak-updates` | Flatpak updates | `stack-flatpak-updates` |

## Fish Function Structure

Each function file follows this template:

```fish
# Usage: stack-<name> [args...]
# One-line description for auto-discovery.
function stack-<name> --description 'One-line description'
    # Argument parsing
    argparse 'h/help' 'y/yes' 'dry-run' -- $argv
    or return 1

    # Help flag
    if set -q _flag_help
        echo "Usage: stack-<name> [args...]"
        echo "  Description of what this does."
        echo ""
        echo "Options:"
        echo "  -y, --yes       Skip confirmation"
        echo "  --dry-run       Show what would happen"
        echo "  -h, --help      Show this help"
        return 0
    end

    # Core logic — either API call or local operation
    __stack_api GET "/api/v2/cli/<endpoint>"
end
```

### Internal Helper: `__stack_api`

Simplified version — no Python, just curl:

```fish
function __stack_api
    set -l method $argv[1]
    set -l path $argv[2]
    set -l body $argv[3]

    set -l host_ip (string split '.' -- $MEDIA_STACK_HOST_IP)[1..4]  # or from universal var
    set -l base_url "https://bearcave.$MEDIA_STACK_HOST_IP.nip.io"
    set -l service_key $MEDIA_STACK_SERVICE_KEY

    set -l curl_opts -sS -X $method --fail-with-body
    if test -n "$service_key"
        set curl_opts $curl_opts -H "X-Api-Key: $service_key"
    end
    if test -n "$body"
        set curl_opts $curl_opts -H 'Content-Type: application/json' -d "$body"
    end

    # Color detection: --color flag or $MEDIA_STACK_COLOR universal var
    if test "$MEDIA_STACK_COLOR" = true; or contains -- --color $argv
        set curl_opts $curl_opts -H "Accept: text/x-terminal"
    end

    curl $curl_opts "$base_url$path"
end
```

### Internal Helper: `__stack_containers`

Live container names for tab completion:

```fish
function __stack_containers
    docker ps -a --format '{{.Names}}' 2>/dev/null | sort
end
```

### Internal Helper: `__stack_arr_app`

Validates arr instance name:

```fish
function __stack_arr_app
    argparse container -- $argv
    or return 1
    test (count $argv) -eq 1; or return 1
    switch $argv[1]
        case radarr sonarr
            echo $argv[1]
        case '*'
            return 1
    end
end
```

## Environment Variables

Set as fish universal variables in `config.fish`:

```fish
# Required — set once
set -U MEDIA_STACK_HOST_IP "192.0.2.1"
set -U MEDIA_STACK_SERVICE_KEY (string match -r '^CONTROL_PANEL_SERVICE_API_KEY=(.*)$' -- (cat $MEDIA_STACK_DIR/.env))[2]
set -U MEDIA_STACK_DIR "/home/bear/TheBearCave"

# Optional
set -U MEDIA_STACK_COLOR true          # Enable colored output (default: auto-detect)
set -U MEDIA_STACK_NO_CONFIRM false    # Skip confirmations globally
```

## Completion Strategy

Manual completions, one file per command in `completions/`:

```fish
# completions/stack-container.fish
complete -c stack-container -f
complete -c stack-container -n __fish_use_subcommand -a restart -d 'Restart a container'
complete -c stack-container -n __fish_use_subcommand -a stop -d 'Stop a container'
complete -c stack-container -n __fish_use_subcommand -a start -d 'Start a container'
complete -c stack-container -n '__fish_seen_subcommand_from restart stop start' -a '(__stack_containers)' -d 'Container'
```

Container names resolved at tab time via `__stack_containers` (live Docker query).

## Install / Uninstall Scripts

### `scripts/install.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FISH_DIR="${HOME}/.config/fish"

# Symlink functions
for f in "$SCRIPT_DIR"/functions/stack-*.fish "$SCRIPT_DIR"/functions/__stack_*.fish; do
    [ -f "$f" ] || continue
    ln -sf "$f" "$FISH_DIR/functions/$(basename "$f")"
done

# Symlink completions
mkdir -p "$FISH_DIR/completions"
for f in "$SCRIPT_DIR"/completions/*.fish; do
    [ -f "$f" ] || continue
    ln -sf "$f" "$FISH_DIR/completions/$(basename "$f")"
done

echo "Installed $(ls "$SCRIPT_DIR"/functions/stack-*.fish 2>/dev/null | wc -l) functions + completions."
```

### `scripts/uninstall.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

FISH_DIR="${HOME}/.config/fish"

# Remove symlinks pointing into this repo
for f in "$FISH_DIR"/functions/stack-*.fish "$FISH_DIR"/functions/__stack_*.fish; do
    [ -L "$f" ] && rm "$f"
done
for f in "$FISH_DIR"/completions/stack-*.fish "$FISH_DIR"/completions/__stack_*.fish; do
    [ -L "$f" ] && rm "$f"
done

echo "Uninstalled fish functions."
```

## Help System

`stack-help` auto-discovers commands by scanning the functions directory:

```fish
function stack-help --description 'List all stack-* commands'
    set -l func_dir (status dirname)/../functions
    echo "Bear Cave media stack — terminal commands"
    echo ""
    for f in "$func_dir"/stack-*.fish
        set -l name (string replace -r '\.fish$' '' -- (basename "$f"))
        set -l desc (string match -r "--description '(.+?)'" -- (cat "$f"))[2]
        printf "  %-45s %s\n" "$name" "$desc"
    end
end
```

## Implementation Plan

### Phase 1: API Endpoints (Django control panel)
1. Create `/api/v2/cli/` URL namespace in `config/urls.py`
2. Create `cli/` Django app with views for each endpoint group
3. Each view calls existing `services.py` functions and formats output
4. Color support via `?color=true` query param or `Accept: text/x-terminal`
5. Add tests for each CLI endpoint

### Phase 2: Fish Functions (API-backed)
1. Create `services/fish-functions/` directory structure
2. Implement `__stack_api` helper (simplified curl)
3. Implement `__stack_containers` and `__stack_arr_app` helpers
4. Write all `stack-*.fish` function files (one per command)
5. Write manual completion files
6. Write `stack-help` with auto-discovery

### Phase 2b: Host Tools (local-only)
1. Create `services/host-tools/` directory structure
2. Implement `__host_helper` utility functions
3. Write all 22 host system `stack-*.fish` function files
4. Write manual completion files
5. Write `stack-help` with auto-discovery

### Phase 3: Tooling
1. Write `scripts/install.sh` (symlink functions + completions)
2. Write `scripts/uninstall.sh` (remove symlinks)
3. Update fish `config.fish` template with universal vars
4. Write README.md with usage, architecture, contributing guide

### Phase 4: Testing
1. Test each CLI endpoint returns correct formatted output
2. Test color vs plain text modes
3. Test each fish function with mock API responses
4. Test completions resolve correctly
5. Test install/uninstall scripts

## Command Count Breakdown

| Category | Count | Location | Notes |
|----------|-------|----------|-------|
| Container & stack mgmt | 11 | fish-functions | Status, restart, resource checks |
| Arr operations | 19 | fish-functions | Queue, imports, search, blocklist, monitoring |
| NzbDAV | 5 | fish-functions | Queue, history, stats, dedup |
| Plex | ~30 | fish-functions | Sessions, libraries, 20+ Butler tasks (separate files) |
| WatchState | 3 | fish-functions | Status, import, history |
| Cleanuparr | 2 | fish-functions | Instances, strikes |
| Log levels | 1 | fish-functions | Check/reset (subcommand) |
| Seerr | 1 | fish-functions | Requests |
| Notifications | 1 | fish-functions | Test Discord |
| Ratings | 2 | fish-functions | IMDb, MDBList |
| Loop remediation | 3 | fish-functions | Candidates, unmonitor, exclude |
| List imports | 4 | fish-functions | letterboxd-import, mdblist-import, trakt-import, plex-import |
| Host system | 22 | host-tools | Disk, memory, kernel, packages, SSH, git |
| Internal helpers | 4 | split | __stack_api + __stack_containers (fish-functions), __host_helper + __host_containers (host-tools) |
| **Total** | **~103** | | |

## Decisions (resolved)

1. **Plex Butler tasks**: Separate files — each `stack-plex-<task>.fish` is its own file, not collapsed into subcommands.
2. **Letterboxd imports**: Collapsed into `stack-letterboxd-import <type> <url>` subcommand. `type` is `list|watchlist|watched|collection|filmography|popular|random`. Tab completion provides the type list.
3. **Host system commands**: Separate directory `services/host-tools/` — these are local-only, no API dependency.
4. **Testing**: Test everything — both API endpoints (Django tests) and fish functions (fishtape + mock curl).
5. **Migration**: Hard cutover — old functions in archive/ are not preserved. New ones replace them entirely.
