# Usage: stack-mdblist-import <mdblist-list-url> [--no-search] [--dry-run] [--limit N]
function stack-mdblist-import --description 'Import a public MDBList list'
    if test (count $argv) -lt 1
        echo "Usage: stack-mdblist-import <url> [--no-search] [--dry-run] [--limit N]" >&2
        return 1
    end
    set -l url $argv[1]
    set -l extra_args ""
    if contains -- --no-search $argv
        set extra_args "$extra_args&no_search=true"
    end
    if contains -- --dry-run $argv
        set extra_args "$extra_args&dry_run=true"
    end
    set -l idx (contains -i -- --limit $argv)
    if test -n "$idx"
        set -l next (math $idx + 1)
        set extra_args "$extra_args&limit=$argv[$next]"
    end
    __stack_api POST "/api/v2/cli/mdblist/import?url=$url$extra_args"
end
