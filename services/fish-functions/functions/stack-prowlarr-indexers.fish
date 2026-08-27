function stack-prowlarr-indexers --description 'Every indexer enabled state + priority'
    set -l url (test -n "$PROWLARR_URL"; and echo "$PROWLARR_URL"; or echo "http://localhost:9696")
    set -l key (test -n "$PROWLARR_API_KEY"; and echo "$PROWLARR_API_KEY"; or echo "")

    fmt_heading "Prowlarr Indexers"
    echo ""

    set -l result (curl -sf "$url/api/v1/indexer" -H "X-Api-Key: $key" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach Prowlarr"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for idx in data:
    name = idx.get('name', '?')
    enabled = '✓' if idx.get('enable') else '✗'
    priority = idx.get('priority', '?')
    print(f'  [{enabled}] {name:<30s} priority={priority}')
" 2>/dev/null
end
