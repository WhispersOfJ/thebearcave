# Usage: stack-plex-markers
# On-demand Plex media-marker audit: counts how many media parts carry a
# delivered intro/credits/ad marker. Markers live in each file's metadata
# (media_parts.extra_data) as JSON under pv: keys, e.g.
#   "pv:credits":{"MediaPartMarkersArray":{...MediaPartMarker[...]}}
# The API exposes these as Marker elements (type=credits/intro/adMarker).
# This command is strictly read-only: it opens the Plex library DB with
# sqlite3 -readonly and never writes.
function stack-plex-markers --description 'Count delivered Plex intro/credits/ad markers (read-only)'
    fmt_heading "Plex Markers"
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

    if not command -q sqlite3
        fmt_error "sqlite3 is required but not installed."
        return 1
    end

    set -l db "$repo/config/plex/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"
    if not test -f "$db"
        echo "  plex library db  "(fmt_status_dot "missing")"  ($db)"
        return 1
    end

    # One read-only pass over media_parts: total analyzed parts plus how many
    # carry each pv: marker key (a part can carry more than one type).
    set -l row (sqlite3 -readonly "$db" "
        SELECT COUNT(*),
               SUM(CASE WHEN extra_data LIKE '%pv:intro%' THEN 1 ELSE 0 END),
               SUM(CASE WHEN extra_data LIKE '%pv:credits%' THEN 1 ELSE 0 END),
               SUM(CASE WHEN extra_data LIKE '%pv:ad%' THEN 1 ELSE 0 END)
        FROM media_parts WHERE extra_data IS NOT NULL;
    ")
    if test $status -ne 0 -o -z "$row"
        fmt_error "Failed to read marker counts from the Plex library DB."
        return 1
    end

    set -l total (string split "|" "$row")[1]
    set -l intro (string split "|" "$row")[2]
    set -l credits (string split "|" "$row")[3]
    set -l ad (string split "|" "$row")[4]

    fmt_kv "analyzed parts" "$total"
    fmt_kv "intro markers" "$intro parts"
    fmt_kv "credits markers" "$credits parts"
    fmt_kv "ad markers" "$ad parts"
    echo ""

    if test "$ad" -gt 0
        fmt_success "Ad markers present — ad detection is delivering."
    else
        fmt_warning "No ad markers yet — ad detection is on ('all items' + asap), but clean content may legitimately have no ad breaks to detect."
    end
    echo "  read-only audit of $db"
end
