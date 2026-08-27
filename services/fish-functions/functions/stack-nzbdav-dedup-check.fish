function stack-nzbdav-dedup-check --description 'Verify NzbDAV dedup config'
    __nzbdav_api GET "dedup-check"
end
