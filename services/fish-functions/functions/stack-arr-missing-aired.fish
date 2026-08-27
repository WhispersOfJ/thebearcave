# Usage: stack-arr-missing-aired <radarr|sonarr>
function stack-arr-missing-aired --description 'Monitored + missing + already aired/released'
    if test (count $argv) -ne 1
        echo "Usage: stack-arr-missing-aired <radarr|sonarr>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end
    __stack_api GET "/api/v2/cli/arr/$app/missing-aired"
end
