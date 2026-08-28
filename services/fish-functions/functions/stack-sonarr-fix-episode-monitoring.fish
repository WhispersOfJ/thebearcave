function stack-sonarr-fix-episode-monitoring --description 'Trigger RefreshMonitoredDownloads on Sonarr'
    set -l url (__arr_api_url sonarr)
    set -l key (__arr_api_key sonarr)
    curl -sf -X POST "$url/api/v3/command" \
        -H "X-Api-Key: $key" \
        -H "Content-Type: application/json" \
        -d '{"name": "RefreshMonitoredDownloads"}' >/dev/null 2>&1
    if test $status -eq 0
        fmt_success "RefreshMonitoredDownloads triggered on sonarr."
    else
        fmt_error "Failed to trigger on sonarr."
    end
end
