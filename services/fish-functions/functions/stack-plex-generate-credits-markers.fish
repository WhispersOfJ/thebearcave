function stack-plex-generate-credits-markers --description 'Generate end-credits markers Butler task'
    __stack_api POST /api/v2/cli/plex/butler/generate-credits-markers
end
