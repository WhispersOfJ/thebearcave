function stack-plex-clean-log-files --description 'Delete old supplemental log files Butler task'
    __stack_api POST /api/v2/cli/plex/butler/clean-log-files
end
