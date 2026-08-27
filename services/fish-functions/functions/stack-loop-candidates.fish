# Usage: stack-loop-candidates <radarr|sonarr>
function stack-loop-candidates --description 'Titles with repeated download failures'
    if test (count $argv) -ne 1
        echo "Usage: stack-loop-candidates <radarr|sonarr>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end

    set -l url (__arr_api_url $app)
    set -l key (__arr_api_key $app)
    fmt_heading "$app — Loop Candidates"
    echo ""

    # Items with multiple failed grabs in history
    set -l result (curl -sf "$url/api/v3/history?pageSize=200&eventType=grabFailed" \
        -H "X-Api-Key: $key" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach $app"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json
from collections import Counter
data = json.load(sys.stdin)
items = data.get('records', []) if isinstance(data, dict) else data
# Count failures per title
fails = Counter()
titles = {}
for item in items:
    title = item.get('sourceTitle', item.get('title', '?'))
    fails[title] += 1
    titles[title] = item
# Show items with 3+ failures
looping = [(t, c) for t, c in fails.most_common() if c >= 3]
if not looping:
    print('  No loop candidates found (no items with 3+ failures).')
else:
    for title, count in looping:
        print(f'  [{count} failures] {title}')
" 2>/dev/null
end
