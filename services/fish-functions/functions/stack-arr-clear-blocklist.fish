# Usage: stack-arr-clear-blocklist <radarr|sonarr> [-y|--yes]
function stack-arr-clear-blocklist --description 'Clear every blocklisted release'
    if test (count $argv) -lt 1
        echo "Usage: stack-arr-clear-blocklist <radarr|sonarr> [-y|--yes]" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end
    if not contains -- -y $argv; and not contains -- --yes $argv
        read -l -P "Clear ALL blocklisted items on $app? [y/N] " confirm
        if test "$confirm" != y -a "$confirm" != Y
            echo "Cancelled."
            return 1
        end
    end

    set -l url (__arr_api_url $app)
    set -l key (__arr_api_key $app)
    set -l endpoint "movie"
    test "$app" = "sonarr"; and set endpoint "series"

    # Get all blocklist items and delete each
    set -l result (curl -sf "$url/api/v3/blocklist?pageSize=1000" -H "X-Api-Key: $key" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach $app"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json, subprocess
data = json.load(sys.stdin)
items = data.get('records', [])
if not items:
    print('  Blocklist is already empty.')
else:
    for item in items:
        bid = item.get('id')
        if bid:
            subprocess.run(['curl', '-sf', '-X', 'DELETE',
                '$url/api/v3/blocklist/$bid',
                '-H', 'X-Api-Key: $key'], capture_output=True)
    print(f'  Cleared {len(items)} blocklisted items.')
" 2>/dev/null
end
