# Internal helper: resolve the API key for an arr app.
# Usage: __arr_api_key <radarr|sonarr|prowlarr>
# Reads <APP>_API_KEY from the environment; fails if unset/empty.
function __arr_api_key
    if test (count $argv) -lt 1
        echo "Usage: __arr_api_key <radarr|sonarr|prowlarr>" >&2
        return 1
    end

    set -l key ""
    switch $argv[1]
        case radarr
            set key "$RADARR_API_KEY"
        case sonarr
            set key "$SONARR_API_KEY"
        case prowlarr
            set key "$PROWLARR_API_KEY"
        case '*'
            echo "Unknown app: $argv[1] (use radarr, sonarr, or prowlarr)" >&2
            return 1
    end

    if test -z "$key"
        echo "API key for $argv[1] not set (expected $argv[1]_API_KEY uppercase in environment)" >&2
        return 1
    end
    echo "$key"
end
