# Usage: stack-status
function stack-status --description 'Show live state/health of every container'
    fmt_heading "Container Status"
    echo ""
    docker ps -a --format '{{.Names}}\t{{.State}}\t{{.Status}}' | sort | while read -l name st elapsed
        set -l dot (fmt_status_dot "$st")
        printf "  %-25s %s\n" "$name" "$dot"
    end
end
