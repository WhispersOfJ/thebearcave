# ============================================================================
# stack-nzbdav.sh — NzbDAV queue/history/stats + mount health
# ============================================================================
# desc: nzbdav queue, history, stats, dedup-check, delete-failures, mount-health
# ============================================================================

# stack-nzbdav-queue — Show NzbDAV current Usenet download queue
stack-nzbdav-queue() {
    __nzbdav_api GET queue
}

# stack-nzbdav-history — NzbDAV download history
stack-nzbdav-history() {
    __nzbdav_api GET history
}

# stack-nzbdav-stats — NzbDAV stats
stack-nzbdav-stats() {
    __nzbdav_api GET stats
}

# stack-nzbdav-dedup-check — canonical implementation lives in stack-disk.sh

# stack-nzbdav-delete-failures — canonical implementation lives in stack-disk.sh

# stack-mount-health — Check FUSE mount health
stack-mount-health() {
    fmt_heading "Mount Health"
    echo ""
    local mount="/mnt/remote/nzbdav"

    if [ -d "$mount" ]; then
        echo "  $mount  $(fmt_status_dot "present")"
    else
        echo "  $mount  $(fmt_status_dot "missing")"
    fi

    # Authoritative check: the rclone sidecar's own healthcheck
    if command -v docker >/dev/null 2>&1; then
        if docker exec nzbdav_rclone mountpoint -q /mnt/remote/nzbdav 2>/dev/null; then
            echo "  rclone mount  $(fmt_status_dot "healthy")"
        else
            echo "  rclone mount  $(fmt_status_dot "dead")"
        fi
    fi

    # Content flows through the WebDAV root served by nzbdav
    local entries
    entries="$(timeout 10 ls "$mount" 2>/dev/null | wc -l)"
    if [ "$entries" -gt 0 ]; then
        echo "  content  $(fmt_status_dot "listing ok")  ($entries entries)"
    else
        echo "  content  $(fmt_status_dot "empty/unreachable")"
    fi
}
