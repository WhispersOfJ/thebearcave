# Usage: stack-arr-toggle-search <radarr|sonarr|all> <on|off>
function stack-arr-toggle-search --description 'Toggle RSS sync + automatic search'
    if test (count $argv) -ne 2
        echo "Usage: stack-arr-toggle-search <radarr|sonarr|all> <on|off>" >&2
        return 1
    end
    set -l enabled true
    test "$argv[2]" = off; and set enabled false
    if test "$argv[1]" = all
        for app in radarr sonarr
            __stack_api POST "/api/v2/cli/arr/$app/command/RssSync"
        end
    else
        set -l app (__stack_arr_app $argv[1])
        or begin; echo "Invalid app: $argv[1]" >&2; return 1; end
        __stack_api POST "/api/v2/cli/arr/$app/command/RssSync"
    end
end
