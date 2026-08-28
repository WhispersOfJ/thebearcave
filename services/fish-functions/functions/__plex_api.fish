# Internal helper: call Plex API directly.
# Usage: __plex_api <METHOD> <path> [json_body]
#   METHOD: GET, POST, PUT, DELETE
#   path: API path (e.g. /status/sessions)
#   json_body: optional JSON body for POST/PUT
#
# Plex runs on host networking, so from the host shell it is reachable on
# localhost:32400. Override with PLEX_URL.
function __plex_api
    if test (count $argv) -lt 2
        echo "Usage: __plex_api <METHOD> <path> [json_body]" >&2
        return 1
    end

    set -l method $argv[1]
    set -l path $argv[2]
    set -l body $argv[3]

    # Determine base URL
    set -l base_url $PLEX_URL
    test -z "$base_url"; and set base_url "http://localhost:32400"

    set -l curl_opts -sS -X $method --fail-with-body

    # Plex uses X-Plex-Token for auth
    if test -n "$PLEX_TOKEN"
        set curl_opts $curl_opts -H "X-Plex-Token: $PLEX_TOKEN"
    end

    if test -n "$body"
        set curl_opts $curl_opts -H 'Content-Type: application/json' -d "$body"
    end

    curl $curl_opts "$base_url$path"
end
