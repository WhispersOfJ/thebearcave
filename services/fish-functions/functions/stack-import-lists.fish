# Usage: stack-import-lists <radarr|sonarr>
function stack-import-lists --description 'Configured import lists and their enabled state'
    if test (count $argv) -ne 1
        echo "Usage: stack-import-lists <radarr|sonarr>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end

    set -l url (__arr_api_url $app)
    set -l key (__arr_api_key $app)
    fmt_heading "$app — Import Lists"
    echo ""

    set -l result (curl -sf "$url/api/v3/importlist" -H "X-Api-Key: $key" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach $app"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('records', [])
if not items:
    print('  No import lists configured.')
else:
    for lst in items:
        name = lst.get('name', '?')
        enabled = '✓' if lst.get('enabled') else '✗'
        ltype = lst.get('listType', '?')
        print(f'  [{enabled}] {name} ({ltype})')
" 2>/dev/null
end
