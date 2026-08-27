# __plex_butler.fish — Trigger a Plex Maintenance (Butler) Task
# Usage: __plex_butler <task-name>
function __plex_butler --description 'Trigger a Plex butler task'
    set -l task $argv[1]
    if test -z "$task"
        echo "Usage: __plex_butler <task-name>" >&2
        return 1
    end

    set -l plex_url (test -n "$PLEX_URL"; and echo "$PLEX_URL"; or echo "http://localhost:32400")
    set -l token (test -n "$PLEX_TOKEN"; and echo "$PLEX_TOKEN"; or echo "")

    if test -z "$token"
        echo "PLEX_TOKEN not set" >&2
        return 1
    end

    curl -sf -X POST "$plex_url/butler?task=$task&X-Plex-Token=$token" >/dev/null 2>&1
    if test $status -eq 0
        fmt_success "Butler task '$task' triggered."
    else
        fmt_error "Failed to trigger butler task '$task'."
        return 1
    end
end
