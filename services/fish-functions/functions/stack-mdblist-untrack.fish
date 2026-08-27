# Usage: stack-mdblist-untrack <list-url>
function stack-mdblist-untrack --description 'Stop syncing a tracked MDBList list'
    if test (count $argv) -ne 1
        echo "Usage: stack-mdblist-untrack <list-url>" >&2
        return 1
    end
    __stack_api DELETE "/api/v2/cli/mdblist/track?url=$argv[1]"
end
