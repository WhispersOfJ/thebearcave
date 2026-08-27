function stack-plex-generate-voice-activity --description 'Generate voice-activity data Butler task'
    __stack_api POST /api/v2/cli/plex/butler/generate-voice-activity
end
