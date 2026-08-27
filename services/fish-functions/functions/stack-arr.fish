# Usage: stack-arr <radarr|sonarr> <rss-sync|search-missing|unstick|unstick-importing>
function stack-arr --description 'Trigger arr command (rss-sync, search-missing, unstick)'
    if test (count $argv) -lt 2
        echo "Usage: stack-arr <radarr|sonarr> <rss-sync|search-missing|unstick|unstick-importing>" >&2
        return 1
    end
    set -l app (__stack_arr_app $argv[1])
    or begin; echo "Invalid app: $argv[1] (use radarr or sonarr)" >&2; return 1; end
    set -l cmd $argv[2]

    # Map fish commands to Arr API command names
    set -l api_cmd
    switch $cmd
        case rss-sync
            set api_cmd RssSync
        case search-missing
            set api_cmd MissingEpisodeSearch
        case unstick
            set api_cmd RefreshMonitoredDownloads
        case unstick-importing
            set api_cmd ManualImport
        case '*'
            echo "Unknown command: $cmd" >&2
            return 1
    end

    # Call Arr API directly
    set -l url (__arr_api_url $app)
    or begin; echo "Cannot determine URL for $app" >&2; return 1; end
    set -l key (__arr_api_key $app)
    or begin; echo "Cannot determine API key for $app" >&2; return 1; end

    set -l result (curl -sf -X POST "$url/api/v3/command" \
        -H "X-Api-Key: $key" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$api_cmd\"}" 2>/dev/null)

    if test $status -eq 0
        fmt_success "$api_cmd triggered on $app."
    else
        fmt_error "Failed to trigger $api_cmd on $app."
        return 1
    end
end
