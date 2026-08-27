function stack-letterboxd-history --description 'Recent Letterboxd sync runs'
    # Letterboxd has no auth API — this checks local sync logs if they exist
    set -l log_dir "/var/log/letterboxd"
    if test -d "$log_dir"
        fmt_heading "Letterboxd Sync History"
        echo ""
        ls -lt "$log_dir"/*.log 2>/dev/null | head -10 | while read -l line
            echo "  $line"
        end
    else
        fmt_heading "Letterboxd"
        echo ""
        echo "  No local sync logs found."
        echo "  Letterboxd sync is not configured in this stack."
    end
end
