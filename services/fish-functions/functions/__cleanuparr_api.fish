# Internal helper: call Cleanuparr API directly.
# Usage: __cleanuparr_api <METHOD> <path> [json_body]
function __cleanuparr_api
    if test (count $argv) -lt 2
        echo "Usage: __cleanuparr_api <METHOD> <path> [json_body]" >&2
        return 1
    end

    set -l method $argv[1]
    set -l path $argv[2]
    set -l body $argv[3]

    set -l base_url $CLEANUPARR_URL
    test -z "$base_url"; and set base_url "http://localhost:11011"

    set -l curl_opts -sS -X $method --fail-with-body

    if test -n "$body"
        set curl_opts $curl_opts -H 'Content-Type: application/json' -d "$body"
    end

    # Callers pass paths without a leading slash — normalize both sides
    set base_url (string trim --chars=/ -- "$base_url")
    set path (string trim --chars=/ -- "$path")
    curl $curl_opts "$base_url/$path"
end
