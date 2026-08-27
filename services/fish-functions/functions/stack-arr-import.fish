# Usage: stack-arr-import <radarr|sonarr> <index>
function stack-arr-import --description 'Import one file by index from import-candidates'
    if test (count $argv) -ne 2
        echo "Usage: stack-arr-import <radarr|sonarr> <index>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end
    __stack_api POST "/api/v2/cli/arr/$app/import/$argv[2]"
end
