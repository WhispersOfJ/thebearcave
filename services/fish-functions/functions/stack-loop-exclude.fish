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
    echo "This function requires the control panel backend (archived). Not yet migrated to direct API calls." && return 1
end
