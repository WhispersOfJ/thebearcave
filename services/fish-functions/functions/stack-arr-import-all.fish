# Usage: stack-arr-import-all <radarr|sonarr>
function stack-arr-import-all --description 'Import every stuck queue file in one go'
    if test (count $argv) -ne 1
        echo "Usage: stack-arr-import-all <radarr|sonarr>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end
    set -l candidates (string split \n -- (__stack_api GET "/api/v2/cli/arr/$app/import-candidates"))
    for line in $candidates
        set -l idx (string match -r '^\s*\[(\d+)\]' -- $line)[2]
        if test -n "$idx"
            echo "Importing #$idx..."
            __stack_api POST "/api/v2/cli/arr/$app/import/$idx"
        end
    end
end
