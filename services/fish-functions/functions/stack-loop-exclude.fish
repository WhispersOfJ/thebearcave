# Usage: stack-loop-exclude <radarr-movie-id> [-y|--yes]
function stack-loop-exclude --description 'Add a Radarr movie to Exclusions'
    if test (count $argv) -lt 1
        echo "Usage: stack-loop-exclude <movie-id> [-y|--yes]" >&2
        return 1
    end
    set -l id $argv[1]
    if not contains -- -y $argv; and not contains -- --yes $argv
        read -l -P "Exclude movie $id from all future grabs? [y/N] " confirm
        if test "$confirm" != y -a "$confirm" != Y
            echo "Cancelled."
            return 1
        end
    end

    set -l url (__arr_api_url radarr)
    set -l key (__arr_api_key radarr)

    # Exclusions are keyed by TMDb id, so resolve the movie first
    set -l movie (curl -sf "$url/api/v3/movie/$id" -H "X-Api-Key: $key" 2>/dev/null)
    if test $status -ne 0
        fmt_error "Cannot fetch movie $id from Radarr"
        return 1
    end
    set -l info (echo "$movie" | python3 -c "
import sys, json
m = json.load(sys.stdin)
print(m.get('tmdbId', ''))
print(m.get('title', '?').replace(chr(10), ' '))
")
    set -l tmdb_id "$info[1]"
    set -l title "$info[2]"

    if test -z "$tmdb_id"
        fmt_error "Movie $id has no TMDb id — cannot add exclusion."
        return 1
    end

    curl -sf -X POST "$url/api/v3/exclusions" \
        -H "X-Api-Key: $key" \
        -H "Content-Type: application/json" \
        -d "{\"tmdbId\": $tmdb_id, \"movieTitle\": \"$title\"}" >/dev/null 2>&1

    if test $status -eq 0
        fmt_success "Excluded '$title' (tmdb $tmdb_id) from all future grabs."
    else
        fmt_error "Failed to add exclusion."
        return 1
    end
end
