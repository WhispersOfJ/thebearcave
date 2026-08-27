# Usage: stack-mdblist-track <list-url> [--label TEXT]
function stack-mdblist-track --description 'Register an MDBList list for nightly sync'
    if test (count $argv) -lt 1
        echo "Usage: stack-mdblist-track <list-url> [--label TEXT]" >&2
        return 1
    end
    set -l url $argv[1]
    set -l label ""
    set -l idx (contains -i -- --label $argv)
    if test -n "$idx"
        set -l next (math $idx + 1)
        set label $argv[$next]
    end

    set -l tracked_file "$HOME/.config/bearcave/mdblist-tracked.txt"
    mkdir -p (dirname "$tracked_file")

    if grep -qF "$url" "$tracked_file" 2>/dev/null
        fmt_warning "Already tracked: $url"
        return 0
    end

    echo "$url|$label" >> "$tracked_file"
    fmt_success "Now tracking: $url${label:+ (label: $label)}"
end
