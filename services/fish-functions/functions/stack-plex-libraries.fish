function stack-plex-libraries --description 'List Plex library names'
    __stack_api GET /api/v2/cli/plex/libraries
end
