# Internal helper: call NzbDAV API directly.
# Usage: __nzbdav_api <METHOD> <mode> [extra_params]
#   METHOD: GET (NzbDAV uses query params, not path-based routing)
#   mode: queue, history, stats, etc.
#   extra_params: optional additional query params
#
# NzbDAV uses SABnzbd-compatible API: /api?mode=<mode>&output=json&apikey=<key>
# Not path-based like other services.
function __nzbdav_api
    if test (count $argv) -lt 2
        echo "Usage: __nzbdav_api <METHOD> <mode> [extra_params]" >&2
        return 1
    end

    set -l method $argv[1]
    set -l mode $argv[2]
    set -l extra $argv[3]

    set -l base_url $NZBDAV_URL
    test -z "$base_url"; and set base_url "http://nzbdav:3000"

    set -l curl_opts -sS -X $method --fail-with-body

    # Build query string: /api?mode=<mode>&output=json&apikey=<key>
    set -l query "mode=$mode&output=json"
    if test -n "$FRONTEND_BACKEND_API_KEY"
        set query "$query&apikey=$FRONTEND_BACKEND_API_KEY"
    end
    if test -n "$extra"
        set query "$query&$extra"
    end

    curl $curl_opts "$base_url/api?$query"
end
