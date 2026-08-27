function stack-cron-list --description 'System timers, user timers, and crontab'
    echo "=== System Timers ==="
    systemctl list-timers --all --no-pager 2>/dev/null | head -20
    echo ""
    echo "=== User Timers ==="
    systemctl --user list-timers --all --no-pager 2>/dev/null | head -20
    echo ""
    echo "=== Crontab ==="
    crontab -l 2>/dev/null || echo "(no crontab)"
end
