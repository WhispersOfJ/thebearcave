# Usage: stack-plex <scan|empty-trash|optimize-db|clean-bundles>
function stack-plex --description 'Trigger a Plex maintenance action'
    if test (count $argv) -ne 1
        echo "Usage: stack-plex <scan|empty-trash|optimize-db|clean-bundles>" >&2
        return 1
    end

    set -l action $argv[1]
    set -l plex_url (test -n "$PLEX_URL"; and echo "$PLEX_URL"; or echo "http://localhost:32400")
    set -l token (test -n "$PLEX_TOKEN"; and echo "$PLEX_TOKEN"; or echo "")

    if test -z "$token"
        echo "PLEX_TOKEN not set" >&2
        return 1
    end

    switch $action
        case scan
            # Refresh all library sections
            set -l sections (curl -sf "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
                | string match -ra 'key="\K[0-9]+' )
            for key in $sections
                curl -sf "$plex_url/library/sections/$key/refresh?X-Plex-Token=$token" >/dev/null 2>&1
            end
            fmt_success "Library scan triggered."

        case empty-trash
            # Empty trash for all libraries
            set -l sections (curl -sf "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
                | string match -ra 'key="\K[0-9]+' )
            for key in $sections
                curl -sf -X PUT "$plex_url/library/sections/$key/emptyTrash?X-Plex-Token=$token" >/dev/null 2>&1
            end
            fmt_success "Trash emptied for all libraries."

        case optimize-db
            curl -sf -X POST "$plex_url/library/optimize?X-Plex-Token=$token" >/dev/null 2>&1
            fmt_success "Database optimization triggered."

        case clean-bundles
            curl -sf -X DELETE "$plex_url/library/bundles?X-Plex-Token=$token" >/dev/null 2>&1
            fmt_success "Bundles cleaned."

        case '*'
            echo "Unknown action: $action (use scan, empty-trash, optimize-db, clean-bundles)" >&2
            return 1
    end
end
