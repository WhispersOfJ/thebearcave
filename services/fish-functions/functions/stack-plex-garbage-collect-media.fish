function stack-plex-garbage-collect-media --description 'Garbage-collect unused media records Butler task'
    __stack_api POST /api/v2/cli/plex/butler/garbage-collect-media
end
