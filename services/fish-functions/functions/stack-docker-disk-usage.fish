function stack-docker-disk-usage --description 'Docker disk usage breakdown'
    __stack_api GET /api/v2/host/disk-health
end
