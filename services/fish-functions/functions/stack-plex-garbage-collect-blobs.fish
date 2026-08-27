function stack-plex-garbage-collect-blobs --description 'Garbage-collect unused metadata blobs Butler task'
    __stack_api POST /api/v2/cli/plex/butler/garbage-collect-blobs
end
