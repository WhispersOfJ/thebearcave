function stack-nzbdav-delete-failures --description 'Delete all Failed entries from NzbDAV history'
    if not contains -- -y $argv; and not contains -- --yes $argv
        read -l -P 'Delete all Failed history entries? [y/N] ' confirm
        if test "$confirm" != y -a "$confirm" != Y
            echo "Cancelled."
            return 1
        end
    end
    __stack_api POST /api/v2/cli/nzbdav/delete-failures
end
