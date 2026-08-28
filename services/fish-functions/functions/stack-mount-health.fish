function stack-mount-health --description 'Check FUSE mount health'
    fmt_heading "Mount Health"
    echo ""
    set -l mount /mnt/remote/nzbdav

    if test -d "$mount"
        echo "  $mount  "(fmt_status_dot "present")
    else
        echo "  $mount  "(fmt_status_dot "missing")
    end

    # Authoritative check: the rclone sidecar's own healthcheck
    if command -q docker
        if docker exec nzbdav_rclone mountpoint -q /mnt/remote/nzbdav 2>/dev/null
            echo "  rclone mount  "(fmt_status_dot "healthy")
        else
            echo "  rclone mount  "(fmt_status_dot "dead")
        end
    end

    # Content flows through the WebDAV root served by nzbdav
    set -l entries (timeout 10 ls "$mount" 2>/dev/null | count)
    if test "$entries" -gt 0
        echo "  content  "(fmt_status_dot "listing ok")"  ($entries entries)"
    else
        echo "  content  "(fmt_status_dot "empty/unreachable")
    end
end
