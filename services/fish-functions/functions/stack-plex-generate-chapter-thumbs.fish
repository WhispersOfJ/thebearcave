function stack-plex-generate-chapter-thumbs --description 'Generate chapter thumbnail files Butler task'
    __stack_api POST /api/v2/cli/plex/butler/generate-chapter-thumbs
end
