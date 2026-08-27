function stack-backlog-status --description 'Every app wanted/missing backlog with throughput ETA'
    __stack_api GET /api/v2/cli/backlog/status
end
