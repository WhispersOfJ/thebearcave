# Usage: stack-loop-exclude <movie-id> [-y|--yes]
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

    # Add to exclusion list via the exclusion endpoint
    curl -sf -X POST "$url/api/v3/exclusion" \
        -H "X-Api-Key: $key" \
        -H "Content-Type: application/json" \
        -d "{\"movieId\": $id, \"reason\": \"Loop candidate\"}" 2>/dev/null

    if test $status -eq 0
        fmt_success "Movie $id added to exclusion list."
    else
        fmt_error "Failed to add exclusion."
        return 1
    end
end
