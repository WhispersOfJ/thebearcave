# Internal helper: call NzbDAV API directly.
# Usage: __nzbdav_api <METHOD> <path> [json_body]
#   METHOD: GET, POST, PUT, DELETE
#   path: API path (e.g. /?mode=get_cats&output=json)
#   json_body: optional JSON body for POST/PUT
#
# NzbDAV runs on the bearcave network at port 3000.
function __nzbdav_api
    if test (count $argv) -lt 2
        echo "Usage: __nzbdav_api <METHOD> <path> [json_body]" >&2
        return 1
    end

    set -l method $argv[1]
    set -l path $argv[2]
    set -l body $argv[3]

    set -l base_url $NZBDAV_URL
    test -z "$base_url"; and set base_url "http://nzbdav:3000"

    set -l curl_opts -sS -X $method --fail-with-body

    if test -n "$FRONTEND_BACKEND_API_KEY"
        set curl_opts $curl_opts -H "X-Api-Key: $FRONTEND_BACKEND_API_KEY"
    end

    if test -n "$body"
        set curl_opts $curl_opts -H 'Content-Type: application/json' -d "$body"
    end

    curl $curl_opts "$base_url$path"
end
