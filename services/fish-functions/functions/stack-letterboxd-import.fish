# Usage: stack-letterboxd-import <type> <url> [--no-search] [--dry-run] [--limit N]
# Types: film, list, watchlist, watched, collection, filmography, popular, random
function stack-letterboxd-import --description 'Import Letterboxd content to Radarr'
    if test (count $argv) -lt 2
        echo "Usage: stack-letterboxd-import <type> <url> [--no-search] [--dry-run] [--limit N]" >&2
        echo "Types: film, list, watchlist, watched, collection, filmography, popular, random" >&2
        return 1
    end
    set -l type $argv[1]
    set -l url $argv[2]
    set -l extra_args ""
    if contains -- --no-search $argv
        set extra_args "$extra_args&no_search=true"
    end
    if contains -- --dry-run $argv
        set extra_args "$extra_args&dry_run=true"
    end
    # Extract --limit N if present
    set -l idx (contains -i -- --limit $argv)
    if test -n "$idx"
        set -l next (math $idx + 1)
        set extra_args "$extra_args&limit=$argv[$next]"
    end
    __stack_api POST "/api/v2/cli/letterboxd/import?type=$type&url=$url$extra_args"
end
