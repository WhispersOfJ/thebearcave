function stack-letterboxd-history --description 'Recent Letterboxd sync runs'
    __stack_api GET /api/v2/cli/letterboxd/history
end
