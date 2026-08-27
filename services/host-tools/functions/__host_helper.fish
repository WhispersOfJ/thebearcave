# Internal helper for host-only operations (no API dependency).
function __host_helper
    set -l cmd $argv[1]
    switch $cmd
        case disk-free
            df -h -x tmpfs -x devtmpfs -x overlay -x squashfs --output=target,size,used,avail,pcent | tail -n +2
        case journal-errors
            journalctl -p err -b --no-pager -o short-iso 2>/dev/null | head -50
        case journal-size
            journalctl --disk-usage 2>/dev/null
        case '*'
            echo "Unknown host helper: $cmd" >&2
            return 1
    end
end
