# Usage: stack-mdblist-import <mdblist-list-url> [--no-search] [--dry-run] [--limit N]
function stack-mdblist-import --description 'Import a public MDBList list'
    if test (count $argv) -lt 1
        echo "Usage: stack-mdblist-import <url> [--no-search] [--dry-run] [--limit N]" >&2
        return 1
    end
    set -l list_url $argv[1]

    set -l mdblist_key (test -n "$MDBLIST_KEY"; and echo "$MDBLIST_KEY"; or echo "")
    if test -z "$mdblist_key"
        fmt_error "MDBLIST_KEY not set"
        return 1
    end

    fmt_heading "MDBList Import"
    echo ""

    # Extract list ID from URL (e.g., https://mdblist.com/lists/user/list-name)
    set -l list_id (echo "$list_url" | grep -oP '\d+$')
    if test -z "$list_id"
        fmt_error "Cannot extract list ID from URL"
        return 1
    end

    set -l result (curl -sf "https://api.mdblist.com/api/lists/$list_id?apikey=$mdblist_key" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot fetch list from MDBList"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d.get('items', d.get('movies', []))
print(f'  List: {d.get(\"name\", \"?\")}')
print(f'  Items: {len(items)}')
for item in items[:10]:
    title = item.get('title', item.get('name', '?'))
    year = item.get('year', '?')
    print(f'    {title} ({year})')
if len(items) > 10:
    print(f'    ... and {len(items) - 10} more')
" 2>/dev/null
end
