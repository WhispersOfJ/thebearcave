# Bash Functions — API-backed CLI

The bash functions are a bash port of the fish `stack-*` library, giving the
same operational surface to bash users. They call the host-published APIs
directly; no proxy or dashboard container is required.

## Layout

```text
services/bash-functions/
├── bearcave-bash.sh            # Sourced from ~/.bashrc; loads .env, fmt_*,
│                               # the guarded docker wrapper, and all stack-*
├── functions/
│   ├── __helpers.sh            # __arr_api, __plex_api, __seerr_api,
│   │                           # __nzbdav_api, __stack_containers, ...
│   ├── stack-arr-1.sh          # backlog, blocklist, recently-added, toggle-search
│   ├── stack-arr-2.sh          # missing, cutoff, import, logs
│   ├── stack-arr-3.sh          # command triggers, backlog status, import lists, prowlarr
│   ├── stack-core.sh           # status, container, restart, top, version, help
│   ├── stack-disk.sh           # config sizes, docker disk, nzbdav dedup/delete-failures
│   ├── stack-lists.sh          # mdblist / letterboxd track / import
│   ├── stack-loop-ratings.sh    # loop candidates, exclude, unmonitor, rating lookups
│   ├── stack-misc.sh           # seerr, notify, backup, worktree, host checks
│   ├── stack-nzbdav.sh         # nzbdav queue, history, stats, mount-health
│   ├── stack-plex-core.sh      # sessions, scan, butler, trash, analyze
│   ├── stack-plex-extra.sh     # duplicates, gc, updates, image-clean
│   ├── stack-plex-markers.sh   # read-only intro/credits/ad marker audit
│   ├── stack-plex-updates.sh   # updates, refresh-libraries, autofix, sonarr fix
│   └── stack-queue.sh          # queue status, queue errors
├── completions/
│   └── stack-completions.sh    # GENERATED — see scripts/gen-bash-completions.sh
└── scripts/
    └── gen-bash-completions.sh # generate / --check completion drift
```

## Setup

Add to `~/.bashrc` (interactive shells only):

```bash
[ -f "$HOME/TheBearCave/services/bash-functions/bearcave-bash.sh" ] && \
    source "$HOME/TheBearCave/services/bash-functions/bearcave-bash.sh"
```

The loader reads `.env` at startup (only setting variables not already set),
defines the `fmt_*` helpers and the guarded `docker` wrapper, then sources every
`functions/__*.sh` and `functions/stack-*.sh`, then the generated completions.

Functions target the direct host ports by default (override with `*_URL` env
vars): Prowlarr `:9696`, Radarr `:7878`, Sonarr `:8989`, NzbDAV `:3000`,
Seerr `:5055`, Plex `:32400`.

## Completion checks

```bash
services/bash-functions/scripts/gen-bash-completions.sh --check   # drift gate
bash -n services/bash-functions/functions/*.sh                   # syntax gate
```

## Relationship to the fish functions

The bash functions are a **parallel port** of `services/fish-functions/`.
The fish functions remain the canonical, installed operational surface today;
the bash port is additive. The planned retirement of the fish functions into a
`docs/services/FISH.md` retirement record is tracked separately and will land
in a follow-up PR after this port is validated in daily use.

## Safety behavior

The `docker` wrapper routes NzbDAV and `nzbdav_rclone` state-changing
operations through `scripts/nzbdav-safe-recreate.sh`, matching the fish
wrapper: recreation is blocked when queued NZBs are present, and `--force` is
explicit and dangerous (queued items are lost). See
[fish-functions safety behavior](fish-functions.md#safety-behavior).
