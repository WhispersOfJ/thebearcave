# Usage: stack-arr-missing-aired <radarr|sonarr>
function stack-arr-missing-aired --description 'Monitored + missing + already aired/released'
    if test (count $argv) -ne 1
        echo "Usage: stack-arr-missing-aired <radarr|sonarr>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end

    set -l url (__arr_api_url $app)
    set -l key (__arr_api_key $app)
    set -l endpoint "movie"
    test "$app" = "sonarr"; and set endpoint "series"
    fmt_heading "$app — Missing + Aired"
    echo ""

    set -l result (curl -sf "$url/api/v3/$endpoint?pageSize=100&monitored=true" \
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
count = 0
for item in items[:30]:
    if item.get('hasFile'):
        continue
    title = item.get('title', '?')
    year = item.get('year', '?')
    print(f'  {title} ({year})')
    count += 1
if count == 0:
    print('  Nothing missing that has aired.')
else:
    print(f'  \n  {count} item(s) missing.')
" 2>/dev/null
end
