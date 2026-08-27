function stack-plex-process-assets --description 'Process pending local assets Butler task'
    __stack_api POST /api/v2/cli/plex/butler/process-assets
end
