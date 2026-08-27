# Usage: stack-arr-backlog <radarr|sonarr>
function stack-arr-backlog --description 'Show the app internal command-queue backlog'
    if test (count $argv) -ne 1
        echo "Usage: stack-arr-backlog <radarr|sonarr>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end

    set -l url (__arr_api_url $app)
    set -l key (__arr_api_key $app)
    fmt_heading "$app Command Queue"
    echo ""

    set -l result (curl -sf "$url/api/v3/command?pageSize=50" -H "X-Api-Key: $key" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach $app"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
cmds = data.get('records', [])
if not cmds:
    print('  Queue is empty.')
else:
    for c in cmds:
        print(f\"  {c.get('name', '?'):<30s} {c.get('status', '?'):<12s} {(c.get('queued', '') or '')[:19]}\")
" 2>/dev/null
end
