# Usage: stack-plex-analyze [library ...]
function stack-plex-analyze --description 'Queue deep media analysis'
    set -l lib $argv[1]
    test -z "$lib"; and set lib all
    set -l plex_url (test -n "$PLEX_URL"; and echo "$PLEX_URL"; or echo "http://localhost:32400")
    set -l token (test -n "$PLEX_TOKEN"; and echo "$PLEX_TOKEN"; or echo "")

    fmt_heading "Plex — Analyze ($lib)"
    echo ""

    set -l ok 0
    set -l failed 0
    if test "$lib" = all
        # Analyze all sections
        set -l sections (curl -sf -H "Accept: application/json" "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
            | python3 -c 'import sys,json; [print(d["key"]) for d in json.load(sys.stdin)["MediaContainer"].get("Directory", [])]' 2>/dev/null)
        for key in $sections
            curl -sf -X POST "$plex_url/library/sections/$key/analyze?X-Plex-Token=$token" >/dev/null 2>&1
            and set ok (math $ok + 1)
            or set failed (math $failed + 1)
        end
    else
        curl -sf -X POST "$plex_url/library/sections/$lib/analyze?X-Plex-Token=$token" >/dev/null 2>&1
        and set ok (math $ok + 1)
        or set failed (math $failed + 1)
    end
    if test $failed -eq 0
        fmt_success "Analysis queued for $ok section(s)."
    else
        fmt_error "Analysis queued for $ok section(s); $failed failed."
        return 1
    end
end
