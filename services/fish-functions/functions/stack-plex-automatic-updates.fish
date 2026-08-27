function stack-plex-automatic-updates --description 'Plex automatic updates Butler task'
    __stack_api POST /api/v2/cli/plex/butler/automatic-updates
end
