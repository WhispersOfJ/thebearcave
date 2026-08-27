# Usage: stack-loop-candidates <radarr|sonarr>
function stack-loop-candidates --description 'Titles with repeated download failures'
    if test (count $argv) -ne 1
        echo "Usage: stack-loop-candidates <radarr|sonarr>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end
    __stack_api GET "/api/v2/cli/loop/candidates?app=$app"
end
