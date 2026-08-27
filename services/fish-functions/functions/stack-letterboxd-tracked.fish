function stack-letterboxd-tracked --description 'Every Letterboxd list currently registered'
    __stack_api GET /api/v2/cli/letterboxd/tracked
end
