# Usage: stack-arr-recently-added <radarr|sonarr> [limit]
function stack-arr-recently-added --description 'Recently added items with file/episode status'
    if test (count $argv) -lt 1
        echo "Usage: stack-arr-recently-added <radarr|sonarr> [limit]" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1]" >&2; return 1; end
    set -l limit 10
    test (count $argv) -ge 2; and set limit $argv[2]
    __stack_api GET "/api/v2/cli/arr/$app/recently-added?limit=$limit"
end
