function stack-disk-config-sizes --description 'Show per-app config directory sizes'
    fmt_heading "Config Directory Sizes"
    echo ""
    set -l dirs /var/lib/docker/containers /opt/arr /config
    for d in $dirs
        if test -d "$d"
            set -l size (du -sh "$d" 2>/dev/null | cut -f1)
            echo "  $d  $size"
        end
    end
    # Also check common config paths
    for app in prowlarr radarr sonarr
        set -l d "/opt/$app/config"
        if test -d "$d"
            set -l size (du -sh "$d" 2>/dev/null | cut -f1)
            echo "  $d  $size"
        end
    end
end
