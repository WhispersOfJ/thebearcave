# Usage: stack-import-lists <radarr|sonarr>
function stack-import-lists --description 'Configured import lists and their enabled state'
    if test (count $argv) -ne 1
        echo "Usage: stack-import-lists <radarr|sonarr>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end
    __stack_api GET "/api/v2/cli/arr/$app/import-lists"
end
