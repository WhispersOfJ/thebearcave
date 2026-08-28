# Usage: stack-letterboxd-untrack <list-url>
function stack-letterboxd-untrack --description 'Stop syncing a tracked Letterboxd list'
    if test (count $argv) -ne 1
        echo "Usage: stack-letterboxd-untrack <list-url>" >&2
        return 1
    end

    set -l tracked_file "$HOME/.config/bearcave/letterboxd-tracked.txt"
    if not test -f "$tracked_file"
        fmt_warning "No lists tracked."
        return 0
    end

    set -l tmp (mktemp)
    grep -vF "$argv[1]" "$tracked_file" >"$tmp" 2>/dev/null
    mv "$tmp" "$tracked_file"
    fmt_success "Stopped tracking: $argv[1]"
end
