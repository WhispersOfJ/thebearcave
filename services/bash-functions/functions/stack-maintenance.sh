# ============================================================================
# stack-maintenance.sh — maintenance-verification digest
# ============================================================================
# desc: nightly maintenance digest — reclaim log, timers, dotfiles, DBs, queue
# ============================================================================

# stack-maintenance-digest — verify the nightly maintenance actually ran
# Prints one line per maintenance surface: the 04:00 disk-reclaim log
# freshness, failed user timers, dotfiles push state, Radarr/Sonarr DB
# health, and the nzbdav queue. Exit 0 when all checks pass (soft warnings
# allowed); exit 1 when something FAILs. Backed by
# scripts/maintenance_digest.py (TODO.md project #1). Read-only — safe to
# run any time; designed for a morning cron after the 04:00 reclaim.
stack-maintenance-digest() {
    if [ "$#" -gt 0 ] && { [ "$1" = "-h" ] || [ "$1" = "--help" ]; }; then
        echo "Usage: stack-maintenance-digest" >&2
        echo "Verify nightly maintenance ran: reclaim log, timers, dotfiles, DBs, queue." >&2
        return 0
    fi
    if [ "$#" -ne 0 ]; then
        echo "Usage: stack-maintenance-digest (no arguments)" >&2
        return 1
    fi

    local repo="${BEARCAVE_REPO_DIR:-}"
    if [ -z "$repo" ]; then
        local self="${BASH_SOURCE[0]}"
        local real
        real="$(readlink -f "$self" 2>/dev/null || echo "$self")"
        repo="$(dirname "$(dirname "$(dirname "$(dirname "$real")")")")"
    fi

    # --repo makes config/ DB paths resolve against the *operational*
    # checkout (the one holding config/radarr + config/sonarr and .env),
    # even when the loader itself was sourced from a worktree clone.
    python3 "$repo/scripts/maintenance_digest.py" --repo "$repo"
}
