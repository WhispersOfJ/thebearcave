function stack-command-queue-summary --description 'Backlog across every arr app at once'
    fmt_heading "Command Queue Summary"
    echo ""
    for app in radarr sonarr
        set -l url (__arr_api_url $app)
        set -l key (__arr_api_key $app)
        set -l count (curl -sf "$url/api/v3/command?pageSize=50" -H "X-Api-Key: $key" 2>/dev/null \
            | python3 -c "import sys,json; d=json.load(sys.stdin); recs=d.get('records',d) if isinstance(d,dict) else d; print(len([c for c in recs if c.get('status')=='queued']))" 2>/dev/null)
        echo "  $app: $count queued commands"
    end
end
