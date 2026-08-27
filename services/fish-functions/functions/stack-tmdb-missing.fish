function stack-tmdb-missing --description 'Scan libraries for items with no TMDb link'
    __stack_api GET /api/v2/host/oom-check
end
