function stack-queue-status --description 'Every app download queue with live-measured speed/ETA'
    fmt_heading "Queue Status"
    echo ""

    for app in radarr sonarr
        set -l url (__arr_api_url $app)
        set -l key (__arr_api_key $app)
        set -l result (curl -sf "$url/api/v3/queue?pageSize=50" -H "X-Api-Key: $key" 2>/dev/null)
        if test $status -ne 0
            echo "  $app: unreachable"
            continue
        end
        echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data.get('records', [])
print(f'  $app: {len(items)} item(s)')
for q in items[:10]:
    title = q.get('title', '?')
    status = q.get('status', '?')
    print(f'    {status}  {title}')
" 2>/dev/null
    end

    # NzbDAV queue
    set -l nzbdav_url (test -n "$NZBDAV_URL"; and echo "$NZBDAV_URL"; or echo "http://localhost:3000")
    echo "  nzbdav:"
    __nzbdav_api GET queue 2>/dev/null | head -10
    echo ""
end
