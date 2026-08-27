# Usage: stack-plex-analyze [library ...]
function stack-plex-analyze --description 'Queue deep media analysis'
    set -l lib $argv[1]
    test -z "$lib"; and set lib "all"
    set -l plex_url (test -n "$PLEX_URL"; and echo "$PLEX_URL"; or echo "http://localhost:32400")
    set -l token (test -n "$PLEX_TOKEN"; and echo "$PLEX_TOKEN"; or echo "")

    fmt_heading "Plex — Analyze ($lib)"
    echo ""

    if test "$lib" = "all"
        # Analyze all sections
        set -l sections (curl -sf "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
            | string match -ra 'key="\K[0-9]+')
        for key in $sections
            curl -sf -X POST "$plex_url/library/sections/$key/analyze?X-Plex-Token=$token" >/dev/null 2>&1
        end
    else
        # Analyze specific section
        curl -sf -X POST "$plex_url/library/sections/$lib/analyze?X-Plex-Token=$token" >/dev/null 2>&1
    end
    fmt_success "Analysis queued."
end
