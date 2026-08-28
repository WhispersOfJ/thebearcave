# Internal helper: call Arr APIs directly (Radarr, Sonarr, Prowlarr).
# Usage: __arr_api <app> <METHOD> <path> [json_body]
#   app: radarr, sonarr, prowlarr
#   METHOD: GET, POST, PUT, DELETE
#   path: API path (e.g. /api/v3/system/status)
#   json_body: optional JSON body for POST/PUT
#
# Defaults target the host-published ports (fish functions run on the host
# shell, where docker service names do not resolve). Override with
# RADARR_URL / SONARR_URL / PROWLARR_URL.
function __arr_api
    if test (count $argv) -lt 3
        echo "Usage: __arr_api <app> <METHOD> <path> [json_body]" >&2
        return 1
    end

    set -l app $argv[1]
    set -l method $argv[2]
    set -l path $argv[3]
    set -l body $argv[4]

    # Determine base URL and API key from environment
    set -l base_url ""
    set -l api_key ""

    switch $app
        case radarr
            set base_url $RADARR_URL
            test -z "$base_url"; and set base_url "http://localhost:7878"
            set api_key $RADARR_API_KEY
        case sonarr
            set base_url $SONARR_URL
            test -z "$base_url"; and set base_url "http://localhost:8989"
            set api_key $SONARR_API_KEY
        case prowlarr
            set base_url $PROWLARR_URL
            test -z "$base_url"; and set base_url "http://localhost:9696"
            set api_key $PROWLARR_API_KEY
        case '*'
            echo "Unknown app: $app (use radarr, sonarr, or prowlarr)" >&2
            return 1
    end

    set -l curl_opts -sS -X $method --fail-with-body

    if test -n "$api_key"
        set curl_opts $curl_opts -H "X-Api-Key: $api_key"
    end

    if test -n "$body"
        set curl_opts $curl_opts -H 'Content-Type: application/json' -d "$body"
    end

    curl $curl_opts "$base_url$path"
end
