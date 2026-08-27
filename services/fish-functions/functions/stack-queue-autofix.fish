# Usage: stack-queue-autofix [-y|--yes]
function stack-queue-autofix --description 'Auto-fix stuck queue items (blocklist+research)'
    if not contains -- -y $argv; and not contains -- --yes $argv
        read -l -P 'Auto-fix stuck queue items? This blocklists failed items. [y/N] ' confirm
        if test "$confirm" != y -a "$confirm" != Y
            echo "Cancelled."
            return 1
        end
    end

    fmt_heading "Queue Autofix"
    echo ""

    for app in radarr sonarr
        set -l url (__arr_api_url $app)
        set -l key (__arr_api_key $app)

        # Get stuck/error items
        set -l result (curl -sf "$url/api/v3/queue?pageSize=100" -H "X-Api-Key: $key" 2>/dev/null)
        if test $status -ne 0
            echo "  $app: unreachable"
            continue
        end

        echo "$result" | python3 -c "
import sys, json, subprocess
data = json.load(sys.stdin)
items = data.get('records', []) if isinstance(data, dict) else data
stuck = [q for q in items if q.get('trackedDownloadStatus') in ('error', 'failed', 'warning')]
if not stuck:
    print(f'  $app: no stuck items')
else:
    for q in stuck:
        title = q.get('title', '?')
        qid = q.get('id')
        # Blocklist the item
        subprocess.run([
            'curl', '-sf', '-X', 'POST',
            '$url/api/v3/blocklist',
            '-H', 'X-Api-Key: $key',
            '-H', 'Content-Type: application/json',
            '-d', json.dumps({'queueId': qid})
        ], capture_output=True)
        print(f'  $app: blocklisted {title}')
    # Trigger MissingEpisodeSearch to re-grab
    subprocess.run([
        'curl', '-sf', '-X', 'POST',
        '$url/api/v3/command',
        '-H', 'X-Api-Key: $key',
        '-H', 'Content-Type: application/json',
        '-d', json.dumps({'name': 'MissingEpisodeSearch'})
    ], capture_output=True)
    print(f'  $app: search triggered for {len(stuck)} items')
" 2>/dev/null
    end
end
