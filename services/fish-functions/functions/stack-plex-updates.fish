function stack-plex-updates --description 'Check for Plex updates (check only)'
    __stack_api GET /api/v2/cli/plex/updates
end
