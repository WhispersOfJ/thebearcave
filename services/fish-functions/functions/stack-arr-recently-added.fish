# Usage: stack-arr-recently-added <radarr|sonarr> [limit]
function stack-arr-recently-added --description 'Recently added items with file/episode status'
    if test (count $argv) -lt 1
        echo "Usage: stack-arr-recently-added <radarr|sonarr> [limit]" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end
    set -l limit 10
    test (count $argv) -ge 2; and set limit $argv[2]

    set -l url (__arr_api_url $app)
    set -l key (__arr_api_key $app)
    set -l endpoint "movie"
    test "$app" = "sonarr"; and set endpoint "series"
    fmt_heading "$app — Recently Added"
    echo ""

    set -l result (curl -sf "$url/api/v3/$endpoint?pageSize=$limit&sortKey=added&sortDirection=descending" \
        -H "X-Api-Key: $key" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach $app"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if isinstance(data, list):
    items = data
else:
    items = data.get('movies', data.get('series', []))
for item in items[:$limit]:
    title = item.get('title', '?')
    year = item.get('year', '?')
    has_file = '✓' if item.get('hasFile') else '✗'
    print(f'  [{has_file}] {title} ({year})')
" 2>/dev/null
end
