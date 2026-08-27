function stack-status --description 'Show live state/health of every container'
    __stack_api GET /api/v2/cli/status
end
