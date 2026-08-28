function stack-backlog-status --description 'Every app wanted/missing backlog'
    fmt_heading "Backlog Status"
    echo ""
    for app in radarr sonarr
        set -l url (__arr_api_url $app)
        set -l key (__arr_api_key $app)

        if test "$app" = radarr
            set -l total (curl -sf "$url/api/v3/movie?pageSize=1" \
                -H "X-Api-Key: $key" 2>/dev/null \
                | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("totalRecords", "?"))' 2>/dev/null)
            set -l missing (curl -sf "$url/api/v3/movie?pageSize=1000" \
                -H "X-Api-Key: $key" 2>/dev/null \
                | python3 -c 'import sys,json; d=json.load(sys.stdin); print(sum(1 for i in d if i.get("monitored") and not i.get("hasFile") and i.get("isAvailable")))' 2>/dev/null)
            echo "  $app: $total monitored, $missing released+missing"
        else
            set -l total (curl -sf "$url/api/v3/series?pageSize=1" \
                -H "X-Api-Key: $key" 2>/dev/null \
                | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("totalRecords", "?"))' 2>/dev/null)
            set -l missing (curl -sf "$url/api/v3/missing?pageSize=1" \
                -H "X-Api-Key: $key" 2>/dev/null \
                | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("totalRecords", "?"))' 2>/dev/null)
            echo "  $app: $total series, $missing aired episodes missing"
        end
    end
end
