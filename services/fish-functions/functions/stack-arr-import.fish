# Usage: stack-arr-import <radarr|sonarr> <index>
function stack-arr-import --description 'Import one file by index from import-candidates'
    if test (count $argv) -ne 2
        echo "Usage: stack-arr-import <radarr|sonarr> <index>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end

    set -l url (__arr_api_url $app)
    set -l key (__arr_api_key $app)

    # Get queue items and find the one at the given index
    set -l result (curl -sf "$url/api/v3/queue?pageSize=100&status=completed" \
        -H "X-Api-Key: $key" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach $app"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json, subprocess
data = json.load(sys.stdin)
items = data.get('records', []) if isinstance(data, dict) else data
idx = int('$argv[2]') - 1
if idx < 0 or idx >= len(items):
    print(f'Invalid index: $argv[2] (have {len(items)} candidates)')
    sys.exit(1)
target = items[idx]
queue_ids = target.get('queueIds', [target.get('id')])
for qid in queue_ids:
    subprocess.run([
        'curl', '-sf', '-X', 'POST',
        '$url/api/v3/command',
        '-H', 'X-Api-Key: $key',
        '-H', 'Content-Type: application/json',
        '-d', json.dumps({'name': 'ManualImport', 'importedIds': [qid]})
    ], capture_output=True)
print(f'Import triggered for: {target.get(\"title\", \"?\")}')
" 2>/dev/null
end
