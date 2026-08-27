# Usage: stack-arr-import-candidates <radarr|sonarr>
function stack-arr-import-candidates --description 'List files ready to manually import'
    if test (count $argv) -ne 1
        echo "Usage: stack-arr-import-candidates <radarr|sonarr>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end
    __stack_api GET "/api/v2/cli/arr/$app/import-candidates"
end
