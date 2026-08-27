# Usage: stack-rating-mdblist <imdb-id>
function stack-rating-mdblist --description 'A title MDBList score + IMDb sub-rating'
    if test (count $argv) -ne 1
        echo "Usage: stack-rating-mdblist <imdb-id>" >&2
        return 1
    end

    set -l mdblist_key (test -n "$MDBLIST_KEY"; and echo "$MDBLIST_KEY"; or echo "")
    if test -z "$mdblist_key"
        fmt_error "MDBLIST_KEY not set"
        return 1
    end

    # MDBList API: lookup by IMDb ID
    set -l result (curl -sf "https://api.mdblist.com/api/tmdb/movie/$argv[1]?apikey=$mdblist_key" 2>/dev/null)
    if test $status -ne 0
        # Try alternative endpoint
        set result (curl -sf "https://mdblist.com/api/$mdblist_key/search?query=$argv[1]" 2>/dev/null)
    end

    if test $status -ne 0
        fmt_error "Cannot reach MDBList API"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if isinstance(d, list) and len(d) > 0:
    item = d[0]
else:
    item = d
print(f'  {item.get(\"title\", \"?\")} ({item.get(\"year\", \"?\")})')
print(f'  MDBList: {item.get(\"score\", \"?\")}')
if item.get('ratings'):
    for r in item['ratings']:
        print(f'  {r.get(\"source\", \"?\")}: {r.get(\"score\", \"?\")}')
" 2>/dev/null
end
