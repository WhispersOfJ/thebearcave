# Usage: stack-letterboxd-untrack <list-url>
function stack-letterboxd-untrack --description 'Stop syncing a tracked Letterboxd list'
    if test (count $argv) -ne 1
        echo "Usage: stack-letterboxd-untrack <list-url>" >&2
        return 1
    end
    echo "This function requires the control panel backend (archived). Not yet migrated to direct API calls." && return 1
end
