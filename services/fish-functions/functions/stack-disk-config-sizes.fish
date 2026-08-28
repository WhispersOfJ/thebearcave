function stack-disk-config-sizes --description 'Show per-app config directory sizes'
    fmt_heading "Config Directory Sizes"
    echo ""
    set -l repo (status dirname)/../..
    set -l base (path resolve "$repo")

    set -l found 0
    for d in "$base"/config/*/ "$base"/data/*/
        if test -d "$d"
            set -l size (du -sh "$d" 2>/dev/null | cut -f1)
            echo "  $d  $size"
            set found 1
        end
    end
    if test $found -eq 0
        echo "  No config/data directories found under $base"
    end

    # Docker's own footprint (needs root for the full picture)
    if test -d /var/lib/docker
        set -l size (sudo -n du -sh /var/lib/docker 2>/dev/null | cut -f1)
        if test -n "$size"
            echo "  /var/lib/docker  $size"
        end
    end
end
