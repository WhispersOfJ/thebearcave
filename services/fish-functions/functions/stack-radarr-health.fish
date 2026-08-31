# Usage: stack-radarr-health
# On-demand Radarr DB integrity check: the orphaned-quality-profile guard
# (landmine #8) and the DB page-footprint/MediaInfo bloat guard (landmine #9).
# Wraps the two preflight scripts so the checks run in one command.
function stack-radarr-health --description 'Check Radarr DB integrity (quality profiles + size)'
    fmt_heading "Radarr Health"
    echo ""
    # Repo root: prefer the path install.sh bakes into conf.d (BEARCAVE_REPO_DIR),
    # which survives this command being autoloaded from a symlinked
    # ~/.config/fish/functions/<name>.fish (status dirname would resolve to the
    # symlink's owning dir, not the repo). Fall back to resolving the real path
    # of this file when not installed (e.g. sourced from a checkout): the file
    # lives at <repo>/services/fish-functions/functions/, i.e. four dirname
    # hops up from the file to the repo root (mirrors conf.d/bearcave-env.fish).
    set -l repo "$BEARCAVE_REPO_DIR"
    if test -z "$repo"
        set -l self (status --current-filename)
        set -l real (readlink -f "$self" 2>/dev/null; or echo "$self")
        set repo (dirname (dirname (dirname (dirname "$real"))))
    end

    set -l db "$repo/config/radarr/radarr.db"
    if not test -f "$db"
        echo "  radarr.db  "(fmt_status_dot "missing")"  ($repo/config/radarr/radarr.db)"
        return 1
    end

    # Each guard is read-only; run them in order and summarize.
    python3 "$repo/scripts/check_radarr_profiles.py"
    set -l profiles $status
    python3 "$repo/scripts/check_radarr_db_size.py"
    set -l size $status

    echo ""
    if test "$profiles" -eq 0 -a "$size" -eq 0
        fmt_success "Radarr healthy — profiles and DB size OK."
    else
        fmt_error "Radarr needs attention — see diagnostics above."
    end
end