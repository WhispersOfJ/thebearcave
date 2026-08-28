# Usage: stack-arr-import-candidates <radarr|sonarr>
function stack-arr-import-candidates --description 'List files ready to manually import'
    if test (count $argv) -ne 1
        echo "Usage: stack-arr-import-candidates <radarr|sonarr>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin
        echo "Invalid app: $argv[1]" >&2
        return 1
    end

    set -l url (__arr_api_url $app)
    set -l key (__arr_api_key $app)
    fmt_heading "$app — Import Candidates"
    echo ""

    # Query queue for completed downloads awaiting import
    set -l result (curl -sf "$url/api/v3/queue?pageSize=100&status=completed" \
        -H "X-Api-Key: $key" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach $app"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data.get('records', []) if isinstance(data, dict) else data
if not items:
    print('  No import candidates.')
else:
    for i, t in enumerate(items, 1):
        title = t.get('title', '?')
        path = t.get('outputPath', t.get('sourcePath', '?'))
        print(f'  [{i}] {title}')
        print(f'       path: {path}')
" 2>/dev/null
end
