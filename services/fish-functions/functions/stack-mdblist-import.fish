# Usage: stack-mdblist-import <numeric-list-id | mdblist.com/lists/<user>/<slug> URL>
function stack-mdblist-import --description 'Import a public MDBList list'
    if test (count $argv) -lt 1
        echo "Usage: stack-mdblist-import <list-id-or-url> [--no-search] [--dry-run] [--limit N]" >&2
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

    # Numeric ids use /api/lists/{id}; site URLs are /lists/<user>/<slug>
    set -l endpoint ""
    if string match -qr '^\d+$' -- "$list_url"
        set endpoint "https://api.mdblist.com/api/lists/$list_url?apikey=$mdblist_key"
    else if string match -qr '^https?://(www\.)?mdblist\.com/lists/[^/?#]+/[^/?#]+' -- "$list_url"
        set -l path (string replace -r '^https?://(www\.)?mdblist\.com/' '' -- "$list_url" | string split '?')[1]
        set endpoint "https://api.mdblist.com/$path?apikey=$mdblist_key"
    else
        fmt_error "Cannot parse list from '$list_url' (use a numeric list id or an mdblist.com/lists/<user>/<slug> URL)"
        return 1
    end

    set -l result (curl -sf "$endpoint" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot fetch list from MDBList"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d.get('items', d.get('movies', []))
print(f\"  List: {d.get('name', '?')}\")
print(f\"  Items: {len(items)}\")
for item in items[:10]:
    title = item.get('title', item.get('name', '?'))
    year = item.get('year', '?')
    print(f'    {title} ({year})')
if len(items) > 10:
    print(f'    ... and {len(items) - 10} more')
" 2>/dev/null
end
