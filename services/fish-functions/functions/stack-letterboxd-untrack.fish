# Usage: stack-letterboxd-untrack <list-url>
function stack-letterboxd-untrack --description 'Stop syncing a tracked Letterboxd list'
    if test (count $argv) -ne 1
        echo "Usage: stack-letterboxd-untrack <list-url>" >&2
        return 1
    end
    __stack_api DELETE "/api/v2/cli/letterboxd/track?url=$argv[1]"
end
