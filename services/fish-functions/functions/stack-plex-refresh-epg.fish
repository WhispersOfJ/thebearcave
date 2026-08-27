function stack-plex-refresh-epg --description 'Refresh Live TV EPG guide data Butler task'
    __stack_api POST /api/v2/cli/plex/butler/refresh-epg
end
