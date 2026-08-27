# Usage: stack-rating-imdb <imdb-id>
function stack-rating-imdb --description 'A title IMDb rating via OMDb'
    if test (count $argv) -ne 1
        echo "Usage: stack-rating-imdb <imdb-id>" >&2
        return 1
    end

    set -l omdb_key (test -n "$OMDB_KEY"; and echo "$OMDB_KEY"; or echo "")
    if test -z "$omdb_key"
        fmt_error "OMDB_KEY not set"
        return 1
    end

    set -l result (curl -sf "http://www.omdbapi.com/?i=$argv[1]&apikey=$omdb_key" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot reach OMDb API"
        return 1
    end

    echo "$result" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if d.get('Response') == 'False':
    print(f'  Not found: {d.get(\"Error\", \"?\")}')
else:
    print(f'  {d.get(\"Title\", \"?\")} ({d.get(\"Year\", \"?\")})')
    print(f'  IMDb: {d.get(\"imdbRating\", \"?\")}/10 ({d.get(\"imdbVotes\", \"?\")} votes)')
    print(f'  Rated: {d.get(\"Rated\", \"?\")}  Runtime: {d.get(\"Runtime\", \"?\")}')
" 2>/dev/null
end
