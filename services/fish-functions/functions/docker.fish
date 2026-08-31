# ============================================================================
# docker.fish — guarded docker compose wrapper (landmine #3)
# ============================================================================
# Intercepts `docker compose` so any nzbdav recreate/restart routes through
# scripts/nzbdav-safe-recreate.sh, which runs the queue guard first and
# refuses when queued NZBs would be wiped on recreate. The landmine
# (docs/landmines.md #3): recreating nzbdav wipes the non-persistent queue
# and blocklists affected items. scripts/update-nzbdav.sh guarded the
# intended update path, but a bare `docker compose up -d nzbdav` bypassed it.
#
# Only operations that touch the nzbdav service AND mutate state (up,
# restart, start, stop, rm, down) are gated; queries (ps, logs, config,
# exec, top) pass straight through to the real docker. `--force` skips the
# guard (DANGEROUS — queued NZBs are wiped and blocklisted).
#
# Install: this file is symlinked into ~/.config/fish/functions/ by
# install.sh, so fish autoloads it and it shadows the `docker` binary for
# the `docker compose` subcommand only. Non-compose `docker` calls (build,
# images, run, …) pass through unchanged.
#
# Disable temporarily: `functions -e docker` (reverts to the binary for the
# session), or rename the file and re-run install.sh.
function docker --description 'Guarded docker: routes nzbdav compose recreates through the queue guard'
    # Only intercept `docker compose ...`; all other docker subcommands
    # (build, images, run, ps, exec, …) go straight to the real binary.
    if test (count $argv) -lt 2; or test "$argv[1]" != compose
        command docker $argv
        return $status
    end

    # `docker compose` — check whether this is a state-mutating op targeting nzbdav.
    set -l sub $argv[2]
    switch $sub
        case up restart start stop rm down
            # Does the arg list target nzbdav or nzbdav_rclone (whose recreate
            # cascades nzbdav)? Exact match —             # service whose recreation cannot touch the queue. If not, pass
            # through ungated.
            set -l hits (string match -e -- nzbdav $argv[3..]; string match -e -- nzbdav_rclone $argv[3..])
            if test (count $hits) -eq 0
                command docker $argv
                return $status
            end
            # Route through the guard wrapper. --force in the args skips the
            # queue guard — strip it before forwarding (compose doesn't know it).
            if contains -- --force $argv
                fmt_warning "--force: skipping queue guard (queued NZBs WILL be wiped)"
                set -l clean
                for a in $argv
                    test "$a" = --force; and continue
                    set -a clean $a
                end
                command docker $clean
                return $status
            end
            set -l guard "$BEARCAVE_REPO_DIR/scripts/nzbdav-safe-recreate.sh"
            if test -z "$BEARCAVE_REPO_DIR"; or not test -x "$guard"
                # Guard not installed / not executable — fall back to the
                # real docker rather than blocking all compose use.
                fmt_warning "nzbdav queue guard not found at $guard — running unguarded"
                command docker $argv
                return $status
            end
            # Pass the compose subcommand + args (drop only `compose`) so the
            # guard sees `up -d nzbdav` etc. $argv[1] is `compose` in the
            # function's own arg list (the command name `docker` is stripped).
            $guard $argv[2..]
            return $status
        case '*'
            # Query / non-mutating compose subcommand — pass through.
            command docker $argv
            return $status
    end
end
