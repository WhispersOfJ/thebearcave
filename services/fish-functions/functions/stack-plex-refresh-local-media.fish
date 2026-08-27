function stack-plex-refresh-local-media --description 'Refresh local media file changes Butler task'
    __stack_api POST /api/v2/cli/plex/butler/refresh-local-media
end
