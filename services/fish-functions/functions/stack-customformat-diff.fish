# Usage: stack-customformat-diff <radarr|sonarr>
function stack-customformat-diff --description 'Diff current custom-format scores against last check'
    if test (count $argv) -ne 1
        echo "Usage: stack-customformat-diff <radarr|sonarr>" >&2
        return 1
    end
    echo "Custom format diff for $argv[1] (implementation via arr-dashboard)"
end
