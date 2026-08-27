function stack-plex-generate-media-index --description 'Generate media index files Butler task'
    __stack_api POST /api/v2/cli/plex/butler/generate-media-index
end
