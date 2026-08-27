# Usage: stack-mdblist-untrack <list-url>
function stack-mdblist-untrack --description 'Stop syncing a tracked MDBList list'
    if test (count $argv) -ne 1
        echo "Usage: stack-mdblist-untrack <list-url>" >&2
        return 1
    end
    echo "This function requires the control panel backend (archived). Not yet migrated to direct API calls." && return 1
end
