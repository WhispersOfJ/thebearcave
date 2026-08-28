# Usage: stack-cutoff-unmet <radarr|sonarr> [limit]
function stack-cutoff-unmet --description 'Items below their quality cutoff'
    if test (count $argv) -lt 1
        echo "Usage: stack-cutoff-unmet <radarr|sonarr> [limit]" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin
        echo "Invalid app: $argv[1]" >&2
        return 1
    end
    set -l limit 10
    test (count $argv) -ge 2; and set limit $argv[2]

    set -l url (__arr_api_url $app)
    set -l key (__arr_api_key $app)
    fmt_heading "$app — Cutoff Unmet"
    echo ""

    # Both Radarr and Sonarr expose unmet-cutoff items natively
    set -l result (curl -sf "$url/api/v3/wanted/cutoff?pageSize=$limit" \
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
    print('  Nothing is below its quality cutoff.')
else:
    for item in records[:$limit]:
        if 'series' in item:
            ep = item.get('episode', {})
            title = item.get('series', {}).get('title', '?')
            label = f\"S{ep.get('seasonNumber', 0):02d}E{ep.get('episodeNumber', 0):02d} {ep.get('title', '?')}\"
        else:
            title = item.get('title', '?')
            label = f\"({item.get('year', '?')})\"
        print(f'  {title} {label}')
    if total > len(records):
        print(f'\\n  ... and {total - len(records)} more')
    print(f'\\n  {total} item(s) below cutoff.')
"
end
