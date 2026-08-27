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
    test -z "$base_url"; and set base_url "http://seerr:5055"

    set -l curl_opts -sS -X $method --fail-with-body

    if test -n "$body"
        set curl_opts $curl_opts -H 'Content-Type: application/json' -d "$body"
    end

    curl $curl_opts "$base_url$path"
end
