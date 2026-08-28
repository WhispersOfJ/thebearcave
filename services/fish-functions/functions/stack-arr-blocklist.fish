# Usage: stack-arr-blocklist <radarr|sonarr> [limit]
function stack-arr-blocklist --description 'Recent blocklisted releases'
    if test (count $argv) -lt 1
        echo "Usage: stack-arr-blocklist <radarr|sonarr> [limit]" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin
        echo "Invalid app: $argv[1]" >&2
        return 1
    end
    set -l limit 20
    test (count $argv) -ge 2; and set limit $argv[2]

    set -l url (__arr_api_url $app)
    set -l key (__arr_api_key $app)
    fmt_heading "$app — Blocklist"
    echo ""

    set -l result (curl -sf "$url/api/v3/blocklist?pageSize=$limit&sortKey=date&sortDirection=descending" \
        -H "X-Api-Key: $key" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach $app"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data.get('records', [])
if not items:
    print('  Blocklist is empty.')
else:
    for item in items[:$limit]:
        title = item.get('title', item.get('sourceTitle', '?'))
        date = (item.get('date', '') or '')[:10]
        print(f'  {date}  {title}')
" 2>/dev/null
end
