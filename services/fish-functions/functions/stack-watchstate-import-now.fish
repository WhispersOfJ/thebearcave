function stack-watchstate-import-now --description 'Queue an out-of-schedule import from Plex'
    __stack_api POST /api/v2/cli/watchstate/import
end
