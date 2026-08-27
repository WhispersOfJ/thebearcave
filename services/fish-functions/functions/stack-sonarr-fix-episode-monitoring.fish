function stack-sonarr-fix-episode-monitoring --description 'Fix unmonitored episodes under monitored series'
    __stack_api POST "/api/v2/cli/arr/sonarr/command/RefreshMonitoredDownloads"
end
