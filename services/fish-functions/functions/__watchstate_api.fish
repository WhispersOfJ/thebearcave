# Internal helper: call WatchState API directly.
# Usage: __watchstate_api <METHOD> <path> [json_body]
function __watchstate_api
    if test (count $argv) -lt 2
        echo "Usage: __watchstate_api <METHOD> <path> [json_body]" >&2
        return 1
    end

    set -l method $argv[1]
    set -l path $argv[2]
    set -l body $argv[3]

    set -l base_url $WATCHSTATE_URL
    test -z "$base_url"; and set base_url "http://watchstate:8080"

    set -l curl_opts -sS -X $method --fail-with-body

    if test -n "$WS_API_KEY"
        set curl_opts $curl_opts -H "X-apikey: $WS_API_KEY"
    end

    if test -n "$body"
        set curl_opts $curl_opts -H 'Content-Type: application/json' -d "$body"
    end

    curl $curl_opts "$base_url$path"
end
