# Usage: stack-arr <radarr|sonarr> <rss-sync|search-missing|unstick|unstick-importing>
function stack-arr --description 'Trigger arr command (rss-sync, search-missing, unstick)'
    if test (count $argv) -lt 2
        echo "Usage: stack-arr <radarr|sonarr> <rss-sync|search-missing|unstick|unstick-importing>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1] (use radarr or sonarr)" >&2; return 1; end
    set -l cmd $argv[2]
    switch $cmd
        case rss-sync
            __stack_api POST "/api/v2/cli/arr/$app/command/RssSync"
        case search-missing
            __stack_api POST "/api/v2/cli/arr/$app/command/MissingEpisodeSearch"
        case unstick
            __stack_api POST "/api/v2/cli/arr/$app/command/RefreshMonitoredDownloads"
        case unstick-importing
            __stack_api POST "/api/v2/cli/arr/$app/command/ManualImport"
        case '*'
            echo "Unknown command: $cmd" >&2
            return 1
    end
end
