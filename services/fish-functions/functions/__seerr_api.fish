# Internal helper: call Seerr API directly.
# Usage: __seerr_api <METHOD> <path> [json_body]
function __seerr_api
    if test (count $argv) -lt 2
        echo "Usage: __seerr_api <METHOD> <path> [json_body]" >&2
        return 1
    end

    set -l method $argv[1]
    set -l path $argv[2]
    set -l body $argv[3]

    set -l base_url $SEERR_URL
    test -z "$base_url"; and set base_url "http://localhost:5055"

    set -l curl_opts -sS -X $method --fail-with-body

    # Seerr requires its own API key (Seerr → Settings → General → API Key)
    if test -z "$SEERR_API_KEY"
        echo "SEERR_API_KEY not set" >&2
        return 1
    end
    set curl_opts $curl_opts -H "X-Api-Key: $SEERR_API_KEY"

    if test -n "$body"
        set curl_opts $curl_opts -H 'Content-Type: application/json' -d "$body"
    end

    # Callers pass paths without a leading slash — normalize both sides
    set base_url (string trim --chars=/ -- "$base_url")
    set path (string trim --chars=/ -- "$path")
    curl $curl_opts "$base_url/$path"
end
