# Internal helper: resolve the base URL for an arr app.
# Usage: __arr_api_url <radarr|sonarr|prowlarr>
# Honors <APP>_URL overrides; defaults target the host-published ports
# (fish functions run on the host shell, where docker service names do
# not resolve).
function __arr_api_url
    if test (count $argv) -lt 1
        echo "Usage: __arr_api_url <radarr|sonarr|prowlarr>" >&2
        return 1
    end

    switch $argv[1]
        case radarr
            test -n "$RADARR_URL"; and echo "$RADARR_URL"; or echo "http://localhost:7878"
        case sonarr
            test -n "$SONARR_URL"; and echo "$SONARR_URL"; or echo "http://localhost:8989"
        case prowlarr
            test -n "$PROWLARR_URL"; and echo "$PROWLARR_URL"; or echo "http://localhost:9696"
        case '*'
            echo "Unknown app: $argv[1] (use radarr, sonarr, or prowlarr)" >&2
            return 1
    end
end
