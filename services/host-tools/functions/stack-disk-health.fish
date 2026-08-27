function stack-disk-health --description 'SMART health summary for every physical disk'
    if not type -q smartctl
        echo "smartctl not found — install smartmontools." >&2
        return 1
    end
    for disk in /dev/sd? /dev/nvme?n?
        test -b "$disk"; or continue
        echo "=== $disk ==="
        sudo smartctl -H "$disk" 2>/dev/null | grep -E "SMART overall|Device Model|SMART Health"
    end
end
