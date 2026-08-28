function stack-nzbdav-history --description 'Show NzbDAV recent download history'
    set -l limit 20
    if test (count $argv) -ge 1
        set limit $argv[1]
    end
    __nzbdav_api GET history "limit=$limit"
end
