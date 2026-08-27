# Usage: stack-arr-backlog <radarr|sonarr>
function stack-arr-backlog --description 'Show the app internal command-queue backlog'
    if test (count $argv) -ne 1
        echo "Usage: stack-arr-backlog <radarr|sonarr>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end
    __stack_api GET "/api/v2/cli/arr/$app/backlog"
end
