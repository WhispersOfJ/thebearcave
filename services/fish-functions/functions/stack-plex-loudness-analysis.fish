function stack-plex-loudness-analysis --description 'Analyze audio loudness Butler task'
    __stack_api POST /api/v2/cli/plex/butler/loudness-analysis
end
