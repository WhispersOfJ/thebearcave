function stack-plex-sessions --description 'Who is watching what right now'
    __stack_api GET /api/v2/cli/plex/sessions
end
