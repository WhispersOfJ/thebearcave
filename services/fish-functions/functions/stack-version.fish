function stack-version --description 'README version + live container count'
    __stack_api GET /api/v2/cli/version
end
