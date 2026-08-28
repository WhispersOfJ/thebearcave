function stack-arr-import-starvation --description 'Why nothing is importing when queue looks empty'
    fmt_heading "Import Starvation Check"
    echo ""
    for app in radarr sonarr
        set -l url (__arr_api_url $app)
        set -l key (__arr_api_key $app)
        set -l lib_endpoint movie
        test "$app" = sonarr; and set lib_endpoint series

        set -l queued (curl -sf "$url/api/v3/queue?pageSize=1" -H "X-Api-Key: $key" 2>/dev/null \
            | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("totalRecords", d.get("total", 0)))' 2>/dev/null)
        set -l library (curl -sf "$url/api/v3/$lib_endpoint?pageSize=1" -H "X-Api-Key: $key" 2>/dev/null \
            | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("totalRecords", d.get("total", 0)))' 2>/dev/null)
        echo "  $app: $queued queue item(s), $library library item(s)"
    end
    echo ""
    echo "  If queue is 0 but grabs are expected: check Prowlarr indexers"
    echo "  (stack-prowlarr-indexers) and NzbDAV queue (stack-nzbdav-queue)."
end
