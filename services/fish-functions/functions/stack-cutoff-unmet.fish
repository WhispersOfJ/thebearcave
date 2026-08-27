# Usage: stack-cutoff-unmet <radarr|sonarr> [limit]
function stack-cutoff-unmet --description 'Items below their quality cutoff'
    if test (count $argv) -lt 1
        echo "Usage: stack-cutoff-unmet <radarr|sonarr> [limit]" >&2
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
    fmt_heading "$app — Cutoff Unmet"
    echo ""

    set -l result (curl -sf "$url/api/v3/$endpoint?pageSize=$limit&monitored=true&cutType=0" \
        -H "X-Api-Key: $key" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach $app"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('movies', data.get('series', []))
for item in items[:$limit]:
    title = item.get('title', '?')
    year = item.get('year', '?')
    quality = item.get('qualityProfileId', '?')
    print(f'  {title} ({year})  profile={quality}')
" 2>/dev/null
end
