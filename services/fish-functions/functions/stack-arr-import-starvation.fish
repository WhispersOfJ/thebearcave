function stack-arr-import-starvation --description 'Why nothing is importing when queue looks empty'
    fmt_heading "Import Starvation Check"
    echo ""
    for app in radarr sonarr
        set -l url (__arr_api_url $app)
        set -l key (__arr_api_key $app)
        set -l queued (curl -sf "$url/api/v3/queue?pageSize=1" -H "X-Api-Key: $key" 2>/dev/null \
            | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total',0))" 2>/dev/null)
        set -l movies (curl -sf "$url/api/v3/movie?pageSize=1" -H "X-Api-Key: $key" 2>/dev/null \
            | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else d.get('total',0))" 2>/dev/null)
        echo "  $app: $queued queue items, $movies library items"
    end
end
