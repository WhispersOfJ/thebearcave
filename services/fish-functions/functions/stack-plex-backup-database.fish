function stack-plex-backup-database --description 'Back up Plex database Butler task'
    __stack_api POST /api/v2/cli/plex/butler/backup-database
end
