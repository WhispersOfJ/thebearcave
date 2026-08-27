function stack-mount-health --description 'Check FUSE mount health'
    fmt_heading "Mount Health"
    echo ""
    set -l mounts /mnt/media /mnt/nzbdav
    for m in $mounts
        if test -d "$m"
            set -l count (find "$m" -maxdepth 1 -type f 2>/dev/null | head -5 | count)
            if test $count -gt 0
                echo "  $m  "(fmt_status_dot "healthy")
            else
                echo "  $m  "(fmt_status_dot "empty")
            end
        else
            echo "  $m  "(fmt_status_dot "missing")
        end
    end
    # Check rclone mount specifically
    if command -q rclone
        set -l running (pgrep -f "rclone.*mount" 2>/dev/null | count)
        if test $running -gt 0
            echo "  rclone  "(fmt_status_dot "running")
        else
            echo "  rclone  "(fmt_status_dot "stopped")
        end
    end
end
