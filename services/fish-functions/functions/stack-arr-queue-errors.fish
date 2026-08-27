function stack-arr-queue-errors --description 'Queue items already flagged as a problem'
    fmt_heading "Queue Errors"
    echo ""
    set -l found 0
    for app in radarr sonarr
        set -l url (__arr_api_url $app)
        set -l key (__arr_api_key $app)
        set -l result (curl -sf "$url/api/v3/queue?pageSize=100" -H "X-Api-Key: $key" 2>/dev/null)
        if test $status -ne 0
            continue
        end
        echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data.get('records', [])
errors = [q for q in items if q.get('trackedDownloadStatus') in ('error', 'warning', 'failed')]
if errors:
    print(f'  $app:')
    for q in errors:
        title = q.get('title', '?')
        status = q.get('trackedDownloadStatus', '?')
        print(f'    {status}  {title}')
" 2>/dev/null | if read -l line
            set found 1
        end
    end
    if test $found -eq 0
        fmt_success "No queue errors across any app."
    end
end
