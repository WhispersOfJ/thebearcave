# Usage: stack-arr-import-all <radarr|sonarr>
function stack-arr-import-all --description 'Import every stuck queue file in one go'
    if test (count $argv) -ne 1
        echo "Usage: stack-arr-import-all <radarr|sonarr>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin
        echo "Invalid app: $argv[1]" >&2
        return 1
    end

    set -l url (__arr_api_url $app)
    set -l key (__arr_api_key $app)

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
if not items:
    print('  No import candidates.')
    sys.exit(0)
imported = 0
for t in items:
    queue_ids = t.get('queueIds', [t.get('id')])
    for qid in queue_ids:
        subprocess.run([
            'curl', '-sf', '-X', 'POST',
            '$url/api/v3/command',
            '-H', 'X-Api-Key: $key',
            '-H', 'Content-Type: application/json',
            '-d', json.dumps({'name': 'ManualImport', 'importedIds': [qid]})
        ], capture_output=True)
    imported += 1
    print(f'  Imported: {t.get(\"title\", \"?\")}')
print(f'\n  {imported} item(s) imported.')
" 2>/dev/null
end
