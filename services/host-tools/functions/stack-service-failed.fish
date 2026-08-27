function stack-service-failed --description 'Failed systemd units'
    echo "=== System ==="
    systemctl --failed --no-pager 2>/dev/null
    echo ""
    echo "=== User ==="
    systemctl --user --failed --no-pager 2>/dev/null
end
