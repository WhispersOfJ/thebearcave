function stack-uptime-report --description 'Uptime, load average, last shutdown'
    echo "=== Uptime ==="
    uptime
    echo ""
    echo "=== Last shutdown ==="
    last -x | head -5
end
