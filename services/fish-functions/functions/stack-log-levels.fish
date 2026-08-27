function stack-log-levels --description 'Show or set log levels for services'
    if test (count $argv) -eq 0
        fmt_heading "Log Levels"
        echo ""
        for app in prowlarr radarr sonarr; do
            set -l level (docker exec "$app" cat /config/Logging/Levels.json 2>/dev/null | grep -oP '"[^"]+"\s*:\s*"[^"]+"' | head -3)
            if test -n "$level"
                echo "  $app:"
                echo "$level" | while read -l l; echo "    $l"; end
            else
                echo "  $app: default"
            end
        end
    else
        echo "Usage: stack-log-levels (read-only — set via Arr web UI)" >&2
        return 1
    end
end
