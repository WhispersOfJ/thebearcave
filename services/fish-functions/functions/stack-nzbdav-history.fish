# Usage: stack-nzbdav-history [limit]
function stack-nzbdav-history --description 'Show NzbDAV recent download history'
    set -l limit 20
    test (count $argv) -ge 1; and set limit $argv[1]
    __stack_api GET "/api/v2/cli/nzbdav/history?limit=$limit"
end
