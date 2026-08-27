function stack-version --description 'Show stack version and container count'
    fmt_heading "Version"
    echo ""
    set -l total (docker ps -a --format '{{.Names}}' | wc -l | tr -d ' ')
    set -l running (docker ps --format '{{.Names}}' | wc -l | tr -d ' ')
    set -l ver "unknown"
    if test -f README.md
        set ver (grep -oP 'Current version: \K\S+' README.md 2>/dev/null; or echo "unknown")
    end
    fmt_kv "Version" "$ver"
    fmt_kv "Running" "$running/$total containers"
end
