function stack-nzbdav-delete-failures --description 'Delete NzbDAV failed downloads'
    __nzbdav_api POST "delete-failures"
end
