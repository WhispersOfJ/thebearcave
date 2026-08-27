function stack-backlog-status --description 'Every app wanted/missing backlog with throughput ETA'
    fmt_heading "Backlog Status"
    echo ""
    for app in radarr sonarr
        set -l url (__arr_api_url $app)
        set -l key (__arr_api_key $app)
        set -l endpoint "movie"
        test "$app" = "sonarr"; and set endpoint "series"
        set -l total (curl -sf "$url/api/v3/$endpoint?pageSize=1&monitored=true" \
            -H "X-Api-Key: $key" 2>/dev/null \
            | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total',0) if isinstance(d,dict) else len(d))" 2>/dev/null)
        set -l missing (curl -sf "$url/api/v3/$endpoint?pageSize=100&monitored=true" \
            -H "X-Api-Key: $key" 2>/dev/null \
            | python3 -c "import sys,json; d=json.load(sys.stdin); items=d if isinstance(d,list) else d.get('movies',d.get('series',[])); print(sum(1 for i in items if not i.get('hasFile')))" 2>/dev/null)
        echo "  $app: $total monitored, $missing missing"
    end
end
