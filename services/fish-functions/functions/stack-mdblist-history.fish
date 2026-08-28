function stack-mdblist-history --description 'Recent MDBList sync runs'
    set -l log_dir /var/log/mdblist
    if test -d "$log_dir"
        fmt_heading "MDBList Sync History"
        echo ""
        ls -lt "$log_dir"/*.log 2>/dev/null | head -10 | while read -l line
            echo "  $line"
        end
    else
        fmt_heading MDBList
        echo ""
        echo "  No local sync logs found."
        echo "  MDBList sync is not configured in this stack."
    end
end
