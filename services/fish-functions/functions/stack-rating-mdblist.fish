# Usage: stack-rating-mdblist <query>
# <query> is an IMDb id (tt...) or a title; uses MDBList's search endpoint.
function stack-rating-mdblist --description 'A title MDBList score + per-source ratings'
    if test (count $argv) -ne 1
        echo "Usage: stack-rating-mdblist <imdb-id-or-title>" >&2
        return 1
    end

    set -l mdblist_key (test -n "$MDBLIST_KEY"; and echo "$MDBLIST_KEY"; or echo "")
    if test -z "$mdblist_key"
        fmt_error "MDBLIST_KEY not set"
        return 1
    end

    set -l payload (python3 -c 'import json, sys; print(json.dumps({"query": sys.argv[1]}))' "$argv[1]")
    set -l result (curl -sf -X POST "https://api.mdblist.com/api/search?apikey=$mdblist_key" \
        -H "Content-Type: application/json" \
        -d "$payload" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach MDBList API"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json
d = json.load(sys.stdin)
results = d if isinstance(d, list) else d.get('results', d.get('movies', []))
if not results:
    print('  No results for that query.')
    sys.exit(0)
item = results[0]
print(f\"  {item.get('title', '?')} ({item.get('year', '?')})\")
score = item.get('score')
print(f\"  MDBList: {score if score is not None else '?'}/100\")
for r in item.get('ratings', []):
    print(f\"  {r.get('source', '?')}: {r.get('score', '?')}\")
"
end
