function stack-plex-clean-cache-files --description 'Delete old cache files Butler task'
    __stack_api POST /api/v2/cli/plex/butler/clean-cache-files
end
