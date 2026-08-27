# Usage: stack-watchstate-history [title] [limit]
function stack-watchstate-history --description 'Watch history, optionally filtered to a title'
    set -l title ""
    set -l limit 20
    if test (count $argv) -ge 1
        set title $argv[1]
    end
    if test (count $argv) -ge 2
        set limit $argv[2]
    end
    if test -n "$title"
        __stack_api GET "/api/v2/cli/watchstate/history?title=$title&limit=$limit"
    else
        __stack_api GET "/api/v2/cli/watchstate/history?limit=$limit"
    end
end
