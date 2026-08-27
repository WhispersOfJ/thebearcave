function stack-plex-upgrade-media-analysis --description 'Re-run analysis for outdated items Butler task'
    __stack_api POST /api/v2/cli/plex/butler/upgrade-media-analysis
end
