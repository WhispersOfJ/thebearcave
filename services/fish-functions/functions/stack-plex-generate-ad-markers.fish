function stack-plex-generate-ad-markers --description 'Generate ad-break markers Butler task'
    __stack_api POST /api/v2/cli/plex/butler/generate-ad-markers
end
