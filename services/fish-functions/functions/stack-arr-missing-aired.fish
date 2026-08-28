# Usage: stack-arr-missing-aired <radarr|sonarr> [limit]
function stack-arr-missing-aired --description 'Monitored, aired/released, and still missing'
    if test (count $argv) -lt 1
        echo "Usage: stack-arr-missing-aired <radarr|sonarr> [limit]" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin
        echo "Invalid app: $argv[1]" >&2
        return 1
    end
    set -l limit 30
    test (count $argv) -ge 2; and set limit $argv[2]

    set -l url (__arr_api_url $app)
    set -l key (__arr_api_key $app)
    fmt_heading "$app — Missing + Aired"
    echo ""

    if test "$app" = radarr
        # Radarr: movies that are monitored, released, and have no file
        set -l result (curl -sf "$url/api/v3/movie?pageSize=1000" \
            -H "X-Api-Key: $key" 2>/dev/null)
        if test $status -ne 0
            fmt_error "Cannot reach $app"
            return 1
        end
        echo "$result" | python3 -c "
import sys, json
try:
    items = json.load(sys.stdin)
except Exception as e:
    print(f'  Error parsing response: {e}')
    sys.exit(1)
missing = [m for m in items if m.get('monitored') and not m.get('hasFile') and m.get('isAvailable')]
if not missing:
    print('  Nothing missing that has been released.')
else:
    for m in missing[:$limit]:
        print(f\"  {m.get('title', '?')} ({m.get('year', '?')})\")
    if len(missing) > $limit:
        print(f'\\n  ... and {len(missing) - $limit} more')
    print(f'\\n  {len(missing)} item(s) missing.')
"
    else
        # Sonarr: the missing endpoint is already monitored + aired episodes
        set -l result (curl -sf "$url/api/v3/missing?pageSize=$limit&sortKey=airDateUtc&sortDirection=descending" \
            -H "X-Api-Key: $key" 2>/dev/null)
        if test $status -ne 0
            fmt_error "Cannot reach $app"
            return 1
        end
        echo "$result" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
except Exception as e:
    print(f'  Error parsing response: {e}')
    sys.exit(1)
records = data.get('records', [])
total = data.get('totalRecords', len(records))
if not records:
    print('  Nothing missing that has aired.')
else:
    for e in records[:$limit]:
        series = e.get('series', {})
        season = e.get('seasonNumber', 0)
        number = e.get('episodeNumber', 0)
        title = e.get('title', '?')
        print(f\"  {series.get('title', '?')} S{season:02d}E{number:02d} {title}\")
    if total > len(records):
        print(f'\\n  ... and {total - len(records)} more')
    print(f'\\n  {total} episode(s) missing.')
"
    end
end
