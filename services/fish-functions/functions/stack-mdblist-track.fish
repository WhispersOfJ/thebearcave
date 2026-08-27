# Usage: stack-mdblist-track <list-url> [--label TEXT]
function stack-mdblist-track --description 'Register an MDBList list for nightly sync'
    if test (count $argv) -lt 1
        echo "Usage: stack-mdblist-track <list-url> [--label TEXT]" >&2
        return 1
    end
    set -l url $argv[1]
    set -l label ""
    set -l idx (contains -i -- --label $argv)
    if test -n "$idx"
        set -l next (math $idx + 1)
        set label $argv[$next]
    end
    echo "This function requires the control panel backend (archived). Not yet migrated to direct API calls." && return 1
end
