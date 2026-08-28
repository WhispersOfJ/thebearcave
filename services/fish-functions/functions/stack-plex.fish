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
            set -l sections (curl -sf -H "Accept: application/json" "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
                | python3 -c 'import sys,json; [print(d["key"]) for d in json.load(sys.stdin)["MediaContainer"].get("Directory", [])]' 2>/dev/null)
            if test -z "$sections"
                fmt_error "Cannot reach Plex or no libraries found."
                return 1
            end
            set -l failed 0
            for key in $sections
                curl -sf -X POST "$plex_url/library/sections/$key/refresh?X-Plex-Token=$token" >/dev/null 2>&1
                or set failed (math $failed + 1)
            end
            if test $failed -eq 0
                fmt_success "Library scan triggered for (count $sections) section(s)."
            else
                fmt_error "Scan triggered for (math (count $sections) - $failed) section(s); $failed failed."
                return 1
            end

        case empty-trash
            # Empty trash for all libraries
            set -l sections (curl -sf -H "Accept: application/json" "$plex_url/library/sections?X-Plex-Token=$token" 2>/dev/null \
                | python3 -c 'import sys,json; [print(d["key"]) for d in json.load(sys.stdin)["MediaContainer"].get("Directory", [])]' 2>/dev/null)
            if test -z "$sections"
                fmt_error "Cannot reach Plex or no libraries found."
                return 1
            end
            set -l failed 0
            for key in $sections
                curl -sf -X PUT "$plex_url/library/sections/$key/emptyTrash?X-Plex-Token=$token" >/dev/null 2>&1
                or set failed (math $failed + 1)
            end
            if test $failed -eq 0
                fmt_success "Trash emptied for (count $sections) section(s)."
            else
                fmt_error "Trash emptied for (math (count $sections) - $failed) section(s); $failed failed."
                return 1
            end

        case optimize-db
            if curl -sf -X POST "$plex_url/library/optimize?X-Plex-Token=$token" >/dev/null 2>&1
                fmt_success "Database optimization triggered."
            else
                fmt_error "Failed to trigger database optimization."
                return 1
            end

        case clean-bundles
            if curl -sf -X DELETE "$plex_url/library/bundles?X-Plex-Token=$token" >/dev/null 2>&1
                fmt_success "Bundles cleaned."
            else
                fmt_error "Failed to clean bundles."
                return 1
            end

        case '*'
            echo "Unknown action: $action (use scan, empty-trash, optimize-db, clean-bundles)" >&2
            return 1
    end
end
