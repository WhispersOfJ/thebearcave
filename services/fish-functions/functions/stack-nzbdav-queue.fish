function stack-nzbdav-queue --description 'Show NzbDAV current Usenet download queue'
    __stack_api GET /api/v2/cli/nzbdav/queue
end
