# Usage: stack-arr-logs <radarr|sonarr|prowlarr> [lines]
function stack-arr-logs --description 'Tail an arr app container log directly'
    if test (count $argv) -lt 1
        echo "Usage: stack-arr-logs <radarr|sonarr|prowlarr> [lines]" >&2
        return 1
    end
    set -l app $argv[1]
    set -l lines 100
    test (count $argv) -ge 2; and set lines $argv[2]
    docker logs --tail $lines -f $app 2>&1
end
